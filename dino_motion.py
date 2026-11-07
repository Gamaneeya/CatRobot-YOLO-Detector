"""Real ROSMASTER M1 motion backend.

ROS2 publishing is performed inside the EXISTING Yahboom Docker motor-driver
container. No direct serial access to the motor controller from the Pi host.
LiDAR runs in an isolated subprocess to protect the camera/web process from
native YDLidar SDK shutdown crashes.
"""
import math
import multiprocessing as mp
import queue
import subprocess
import threading
import time

CMD_VEL = '/cmd_vel'
BRIDGE = r'''
import math, os, select, sys, time
import rclpy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

# The M1 camera gimbal is controlled through the EXISTING ROS2 driver.
# Different Yahboom driver releases name the two message fields differently.
try:
    from yahboomcar_msgs.msg import ServoControl
except ImportError:
    ServoControl=None

TOPIC=sys.argv[1]
rclpy.init()
node=rclpy.create_node('dino_follow_sole_motor_writer')
pub=None
buzzer=None
servo_pub=None
servo_fields=None
try:
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        rclpy.spin_once(node,timeout_sec=0.1)
        if node.get_subscriptions_info_by_topic(TOPIC):break
    subscribers=node.get_subscriptions_info_by_topic(TOPIC)
    others=node.get_publishers_info_by_topic(TOPIC)
    if not subscribers:
        print('ERROR NO_MOTOR_SUBSCRIBER',flush=True);sys.exit(3)
    if any(s.topic_type!='geometry_msgs/msg/Twist' for s in subscribers):
        print('ERROR BAD_MOTOR_TOPIC_TYPE',flush=True);sys.exit(4)
    if others:
        print('ERROR OTHER_CMD_VEL_PUBLISHERS '+str(len(others)),flush=True);sys.exit(5)
    pub=node.create_publisher(Twist,TOPIC,10)
    buzzer=node.create_publisher(Bool,'/Buzzer',10)
    print('READY /cmd_vel subscribers='+str(len(subscribers)),flush=True)
    # Do not move the gimbal at startup. Discover the driver's real message type.
    if ServoControl is None:
        print('SERVO_UNAVAILABLE missing yahboomcar_msgs/msg/ServoControl',flush=True)
    else:
        available=set(ServoControl.get_fields_and_field_types())
        if {'s1','s2'} <= available:
            servo_fields=('s1','s2')
        elif {'servo_s1','servo_s2'} <= available:
            servo_fields=('servo_s1','servo_s2')
        else:
            print('SERVO_UNAVAILABLE unsupported_fields='+','.join(sorted(available)),flush=True)
        if servo_fields:
            servo_pub=node.create_publisher(ServoControl,'/Servo',10)
    print('BUZZER_TOPIC /Buzzer',flush=True)
    buf=b''; v=0.; w=0.; last=0.; next_send=0.; next_check=time.monotonic()+.6
    servo_ready_reported=False
    while rclpy.ok():
        rclpy.spin_once(node,timeout_sec=0)
        if select.select([sys.stdin],[],[],0)[0]:
            data=os.read(sys.stdin.fileno(),4096)
            if not data:break
            buf+=data
            if len(buf)>16384:buf=b'';v=w=0.;last=0.
            while b'\n' in buf:
                raw,buf=buf.split(b'\n',1)
                try:
                    parts=raw.decode('ascii').split()
                    if parts==['STOP']:
                        v=w=0.;last=0.
                    elif len(parts)==3 and parts[0]=='VEL':
                        nv,nw=map(float,parts[1:])
                        if not (math.isfinite(nv) and math.isfinite(nw)):raise ValueError()
                        v=max(-.07,min(.07,nv))
                        w=max(-.22,min(.22,nw))
                        last=time.monotonic()
                    elif len(parts)==2 and parts[0]=='BEEP':
                        if parts[1] not in ('0','1'):raise ValueError()
                        msg=Bool();msg.data=(parts[1]=='1')
                        buzzer.publish(msg)
                    elif len(parts)==3 and parts[0]=='SERVO':
                        if not servo_pub or not servo_fields:
                            print('SERVO_UNAVAILABLE no_message_type',flush=True)
                        elif not node.get_subscriptions_info_by_topic('/Servo'):
                            print('SERVO_UNAVAILABLE no_driver_subscriber',flush=True)
                        else:
                            s1,s2=map(int,parts[1:])
                            if not (0<=s1<=180 and 0<=s2<=180):raise ValueError()
                            m=ServoControl()
                            setattr(m,servo_fields[0],s1)
                            setattr(m,servo_fields[1],s2)
                            servo_pub.publish(m)
                            print('SERVO_SENT s1='+str(s1)+' s2='+str(s2),flush=True)
                    else:raise ValueError()
                except (ValueError,UnicodeError):
                    v=w=0.;last=0.
        now=time.monotonic()
        if now>=next_check:
            other=[p for p in node.get_publishers_info_by_topic(TOPIC)
                   if p.node_name!=node.get_name()]
            if other:
                print('ERROR SECOND_MOTOR_WRITER',flush=True);break
            if not node.get_subscriptions_info_by_topic(TOPIC):
                print('ERROR MOTOR_SUBSCRIBER_LOST',flush=True);break
            if servo_fields and servo_pub:
                ss=node.get_subscriptions_info_by_topic('/Servo')
                if any(s.topic_type=='yahboomcar_msgs/msg/ServoControl' for s in ss):
                    if not servo_ready_reported:
                        print('SERVO_READY fields='+','.join(servo_fields),flush=True)
                        servo_ready_reported=True
                elif servo_ready_reported:
                    print('SERVO_UNAVAILABLE no_driver_subscriber',flush=True)
                    servo_ready_reported=False
            next_check=now+.5
        if now>=next_send:
            m=Twist()
            if now-last<=.38:
                m.linear.x=v;m.angular.z=w
            pub.publish(m)
            next_send=now+.05
        time.sleep(.008)
finally:
    if pub:
        try:
            m=Twist()
            for i in range(10):
                pub.publish(m);rclpy.spin_once(node,timeout_sec=.01)
                time.sleep(.02)
        except Exception:pass
    try:node.destroy_node();rclpy.shutdown()
    except Exception:pass
'''


class DockerMotor:
    """Starts precisely one active ROS2 /cmd_vel publisher inside Docker."""
    def __init__(self, container='affectionate_lamport', domain=62):
        self._lock=threading.RLock()
        self._ready=False
        self._closed=False
        self._servo_ready=False
        self._servo_warning=False
        self.error=None
        self._out=queue.Queue()
        shell=(
            'source /opt/ros/humble/setup.bash; '
            'source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash; '
            f'export ROS_DOMAIN_ID={int(domain)}; '
            'export ROS_LOCALHOST_ONLY=1; '
            'exec /usr/bin/python3 -u -c "$1" "$2"'
        )
        cmd=['sudo','-n','docker','exec','-i',container,'/bin/bash','-lc',
             shell,'dino_bridge',BRIDGE,CMD_VEL]
        try:
            self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,bufsize=1,text=True)
        except Exception as exc:
            raise RuntimeError('Could not launch Docker motor bridge: '+str(exc)) from exc
        self._read_thread=threading.Thread(target=self._drain,daemon=True)
        self._read_thread.start()
        deadline=time.monotonic()+18
        while time.monotonic()<deadline:
            try:line=self._out.get(timeout=.2)
            except queue.Empty:
                if self.proc.poll() is not None:break
                continue
            if line.startswith('READY /cmd_vel'):
                self._ready=True;print('[MOTOR]',line,flush=True);return
            if line.startswith('ERROR'):
                self.error=line;break
        self.close()
        raise RuntimeError('ROS2 motor cannot arm: '+str(self.error or 'no READY response'))

    def _drain(self):
        try:
            for raw in self.proc.stdout:
                line=raw.strip()
                if line.startswith('ERROR'):
                    self.error=line;self._ready=False
                    print('[MOTOR ERROR]',line,flush=True)
                elif line.startswith('SERVO_READY'):
                    self._servo_ready=True
                    print('[SERVO]',line,flush=True)
                elif line.startswith('SERVO_UNAVAILABLE'):
                    self._servo_ready=False
                    print('[SERVO]',line,flush=True)
                elif line.startswith('READY'):
                    self._out.put(line)
                elif line:
                    print('[MOTOR DOCKER]',line,flush=True)
                if line.startswith('ERROR'):self._out.put(line)
        finally:
            self._ready=False
            self._servo_ready=False
            if not self._closed and not self.error:
                self.error='Motor bridge exited unexpectedly'
                print('[MOTOR ERROR]',self.error,flush=True)

    @property
    def ready(self):
        return self._ready and not self._closed and self.proc.poll() is None

    def _write(self,text):
        with self._lock:
            if not self.ready:
                raise RuntimeError(self.error or 'ROS2 bridge disconnected')
            try:self.proc.stdin.write(text+'\n');self.proc.stdin.flush()
            except (BrokenPipeError,OSError,ValueError) as exc:
                self._ready=False
                self.error='ROS2 bridge write failed'
                raise RuntimeError(self.error) from exc

    def velocity(self,v,w):
        if not (math.isfinite(v) and math.isfinite(w)):
            v=w=0.
        self._write(f'VEL {max(-.07,min(.07,v)):.4f} {max(-.22,min(.22,w)):.4f}')

    def stop(self):
        if self.ready:
            try:self._write('STOP')
            except RuntimeError:pass

    def beep(self,on):
        if self.ready:self._write('BEEP '+('1' if on else '0'))

    @property
    def servo_ready(self):
        return self.ready and self._servo_ready

    def servo(self, pan, tilt):
        """Move real PTZ by publishing BOTH angles to /Servo inside Docker."""
        if not self.servo_ready:
            if not self._servo_warning:
                print('[SERVO] NOT READY: check /Servo topic, keep camera still',flush=True)
                self._servo_warning=True
            return False
        self._write(f'SERVO {int(pan)} {int(tilt)}')
        return True

    def close(self):
        with self._lock:
            if self._closed:return
            if self.ready:
                try:
                    self.proc.stdin.write('STOP\n');self.proc.stdin.flush()
                    time.sleep(.1)
                    self.proc.stdin.close()
                except Exception:pass
            self._closed=True
        try:self.proc.wait(timeout=2.5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:self.proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=1)
        print('[MOTOR] Shutdown: zero velocity requested',flush=True)


def _lidar_worker(port,angle,stop,results):
    """Separate process: native SDK crashes do not bring down motor/web process."""
    from tmini_plus_lidar import TminiPlusReader
    lidar=TminiPlusReader(port,front_angle_deg=angle)
    try:
        lidar.start()
        while not stop.wait(.12):
            status=lidar.snapshot()
            item=(time.monotonic(),status)
            try:results.put_nowait(item)
            except queue.Full:
                try:results.get_nowait()
                except queue.Empty:pass
                try:results.put_nowait(item)
                except queue.Full:pass
    finally:
        lidar.close()


class IsolatedLidar:
    def __init__(self,port='/dev/ttyUSB1',angle=0.):
        self.ctx=mp.get_context('spawn')
        self.stop_event=self.ctx.Event()
        self.queue=self.ctx.Queue(maxsize=2)
        self.proc=self.ctx.Process(target=_lidar_worker,
                         args=(port,angle,self.stop_event,self.queue),daemon=True)
        self.proc.start()
        self._last=None

    def snapshot(self):
        try:
            while True:self._last=self.queue.get_nowait()
        except queue.Empty:pass
        if not self.proc.is_alive():
            return {'clear':False,'reason':'LIDAR PROCESS STOPPED',
                    'scan_age_s':None,'front_min_m':None,'left_min_m':None,
                    'right_min_m':None}
        if self._last is None:
            return {'clear':False,'reason':'WAITING FOR LIDAR',
                    'scan_age_s':None,'front_min_m':None,'left_min_m':None,
                    'right_min_m':None}
        at,status=self._last
        if time.monotonic()-at>.55:
            return dict(status,clear=False,reason='STALE LIDAR IPC')
        return status

    def close(self):
        self.stop_event.set()
        self.proc.join(timeout=2.5)
        if self.proc.is_alive():
            self.proc.terminate();self.proc.join(timeout=1.5)
        if self.proc.is_alive():self.proc.kill();self.proc.join(timeout=1)
        try:self.queue.close()
        except Exception:pass


def follow_motion(center, area, target_visible, close_area=.22):
    """Use box size only to STOP close-up, never as an actual distance sensor."""
    if not target_visible:
        return (0.,0.,'NO DINO - STOP')
    if not (math.isfinite(center) and math.isfinite(area)):
        return (0.,0.,'BAD DETECTION - STOP')
    if area>=close_area:
        return (0.,0.,'DINO CLOSE - STOP')
    if center<.43:
        return (0.,.19,'TURN LEFT')
    if center>.57:
        return (0.,-.19,'TURN RIGHT')
    return (.055,0.,'FOLLOW FORWARD')
