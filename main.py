"""
tellotracker:
Allows manual operation of the drone and demo tracking mode.
Requires mplayer to record/save video.
Controls:
- tab to lift off
- WASD to move the drone
- space/shift to ascend/descent slowly
- Q/E to yaw slowly
- arrow keys to ascend, descend, or yaw quickly
- backspace to land, or P to palm-land
- enter to take a picture
- R to start recording video, R again to stop recording
  (video and photos will be saved to a timestamped file in ~/Pictures/)
- Z to toggle camera zoom state
  (zoomed-in widescreen or high FOV 4:3)
- T to toggle tracking
@author Leonie Buckley, Saksham Sinha and Jonathan Byrne
@copyright 2018 see license file for details
"""
import time
import datetime
import os
import tellopy
import numpy
import av
import cv2
from pynput import keyboard
from tracker import Tracker
from trackingparams import TrackingParams

def main():
    """ Create a tello controller and show the video feed."""
    tello_track = TelloCV()

    for packet in tello_track.container.demux((tello_track.vid_stream,)):
        for frame in packet.decode():
            image = tello_track.process_frame(frame)
            cv2.imshow('tello', image)
            _ = cv2.waitKey(1) & 0xFF

class TelloCV(object):
    """
    TelloTracker builds keyboard controls on top of TelloPy as well
    as generating images from the video stream and enabling opencv support
    """

    def __init__(self):
        self.prev_flight_data = None
        self.record = False
        self.tracking = False
        self.keydown = False
        self.date_fmt = '%Y-%m-%d_%H%M%S'
        self.speed = 20
        self.turn_speed = TrackingParams.turn_speed
        self.move_speed = TrackingParams.move_speed
        self.drone = tellopy.Tello()
        self.init_drone()
        self.init_controls()
        # container for processing the packets into frames
        self.container = av.open(self.drone.get_video_stream())
        self.vid_stream = self.container.streams.video[0]
        self.out_file = None
        self.out_stream = None
        self.out_name = None
        self.start_time = time.time()

        self.last_cmd = ""
        self.tracker = Tracker(self.vid_stream.height,
                               self.vid_stream.width,
                               TrackingParams.color_lower, TrackingParams.color_upper)

    def init_drone(self):
        """Connect, uneable streaming and subscribe to events"""
        # self.drone.log.set_level(2)
        self.drone.connect()
        self.drone.start_video()
        self.drone.subscribe(self.drone.EVENT_FLIGHT_DATA,
                             self.flight_data_handler)
        self.drone.subscribe(self.drone.EVENT_FILE_RECEIVED,
                             self.handle_flight_received)


    def on_press(self, keyname):
        """handler for keyboard listener"""
        if self.keydown:
            return
        try:
            self.keydown = True
            keyname = str(keyname).strip('\'')
            print('+' + keyname)
            if keyname == 'Key.esc':
                self.drone.quit()
                exit(0)
            if keyname in self.controls:
                key_handler = self.controls[keyname]
                if isinstance(key_handler, str):
                    getattr(self.drone, key_handler)(self.speed)
                else:
                    key_handler(self.speed)
        except AttributeError:
            print('special key {0} pressed'.format(keyname))

    def on_release(self, keyname):
        """Reset on key up from keyboard listener"""
        self.keydown = False
        keyname = str(keyname).strip('\'')
        print('-' + keyname)
        if keyname in self.controls:
            key_handler = self.controls[keyname]
            if isinstance(key_handler, str):
                getattr(self.drone, key_handler)(0)
            else:
                key_handler(0)

    def init_controls(self):
        """Define keys and add listener"""
        self.controls = {
            'w': 'forward',
            's': 'backward',
            'a': 'left',
            'd': 'right',
            'Key.space': 'up',
            'Key.shift': 'down',
            'Key.shift_r': 'down',
            'q': 'counter_clockwise',
            'e': 'clockwise',
            'i': lambda speed: self.drone.flip_forward(),
            'k': lambda speed: self.drone.flip_back(),
            'j': lambda speed: self.drone.flip_left(),
            'l': lambda speed: self.drone.flip_right(),
            # arrow keys for fast turns and altitude adjustments
            'Key.left': lambda speed: self.drone.counter_clockwise(speed),
            'Key.right': lambda speed: self.drone.clockwise(speed),
            'Key.up': lambda speed: self.drone.up(speed),
            'Key.down': lambda speed: self.drone.down(speed),
            'Key.tab': lambda speed: self.drone.takeoff(),
            'Key.backspace': lambda speed: self.drone.land(),
            'p': lambda speed: self.palm_land(speed),
            't': lambda speed: self.toggle_tracking(speed),
            'r': lambda speed: self.toggle_recording(speed),
            'z': lambda speed: self.toggle_zoom(speed),
            'Key.enter': lambda speed: self.take_picture(speed)
        }
        self.key_listener = keyboard.Listener(on_press=self.on_press,
                                              on_release=self.on_release)
        self.key_listener.start()
        # self.key_listener.join()

    def process_frame(self, frame):
        """convert frame to cv2 image and show"""
        image = cv2.cvtColor(numpy.array(frame.to_image()), cv2.COLOR_RGB2BGR)
        image = self.write_hud(image)
        if self.record:
            self.record_vid(frame)

        xoff, yoff, land, found, object_radius = self.tracker.track(image, TrackingParams.landing_radius)



        image = self.tracker.draw_arrows(image)

        distance = TrackingParams.allowed_distance
        cmd = ""
        if self.tracking:
            if land:
                self.drone.land()
            elif not found:
                cmd = "clockwise"
                # make the drone slowly rise into the air
                # self.drone.up(TrackingParams.track_up)
            elif yoff < -distance:
                cmd = "down"
            elif yoff > distance:
                cmd = "up"
            elif xoff < -distance:
                cmd = "counter_clockwise"
            elif xoff > distance:
                cmd = "clockwise"
            else:
                cmd = "forward"
        if cmd != self.last_cmd:
            if self.last_cmd != "":
                print(self.last_cmd)
                getattr(self.drone, self.last_cmd)(0)
            self.last_cmd = cmd

            if cmd != "":
                print("track command:", cmd)
                if cmd == "land":
                    getattr(self.drone, cmd)
                else:
                    if cmd == "forward":
                        # drone will move forward at speed set in tracking params
                        getattr(self.drone, cmd)(TrackingParams.move_speed)
                    else:
                        # drone SHOULD stop moving forward
                        getattr(self.drone, "forward")(0)
                        if not found:
                            tempturn_speed = 50
                        else:
                            # TODO line 203-206 is untested code
                            if object_radius > 150:
                                tempturn_speed = 10
                            else:
                                tempturn_speed = 20

                                print("***** tempturn_speed = %s" % tempturn_speed)
                                getattr(self.drone, cmd)(tempturn_speed)


        return image

    def write_hud(self, frame):
        """Draw drone info, tracking and record on frame"""
        stats = self.prev_flight_data.split('|')
        stats.append("Tracking:" + str(self.tracking))
        if self.drone.zoom:
            stats.append("VID")
        else:
            stats.append("PIC")
        if self.record:
            diff = int(time.time() - self.start_time)
            mins, secs = divmod(diff, 60)
            stats.append("REC {:02d}:{:02d}".format(mins, secs))

        for idx, stat in enumerate(stats):
            text = stat.lstrip()
            cv2.putText(frame, text, (0, 30 + (idx * 30)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 255, 0), lineType=30)
        return frame

    def toggle_recording(self, speed):
        """Handle recording keypress, creates output stream and file"""
        if speed == 0:
            return
        self.record = not self.record

        if self.record:
            from pathlib import Path
            home = str(Path.home())
            datename = [home, datetime.datetime.now().strftime(self.date_fmt)]
            self.out_name = '{}\\tello-{}.mp4'.format(*datename)
            print("Outputting video to:", self.out_name)
            self.out_file = av.open(self.out_name, 'w')
            self.start_time = time.time()
            self.out_stream = self.out_file.add_stream(
                'mpeg4', self.vid_stream.rate)
            self.out_stream.pix_fmt = 'yuv420p'
            self.out_stream.width = self.vid_stream.width
            self.out_stream.height = self.vid_stream.height

        if not self.record:
            print("Video saved to ", self.out_name)
            self.out_file.close()
            self.out_stream = None

    def record_vid(self, frame):
        """
        convert frames to packets and write to file
        """
        new_frame = av.VideoFrame(
            width=frame.width, height=frame.height, format=frame.format.name)
        for i in range(len(frame.planes)):
            new_frame.planes[i].update(frame.planes[i])
        pkt = None
        try:
            pkt = self.out_stream.encode(new_frame)
        except IOError as err:
            print("encoding failed: {0}".format(err))
        if pkt is not None:
            try:
                self.out_file.mux(pkt)
            except IOError:
                print('mux failed: ' + str(pkt))

    def take_picture(self, speed):
        """Tell drone to take picture, image sent to file handler"""
        if speed == 0:
            return
        self.drone.take_picture()

    def palm_land(self, speed):
        """Tell drone to land"""
        if speed == 0:
            return
        self.drone.palm_land()

    def toggle_tracking(self, speed):
        """ Handle tracking keypress"""
        if speed == 0:  # handle key up event
            return
        self.tracking = not self.tracking
        print("tracking:", self.tracking)
        return

    def toggle_zoom(self, speed):
        """
        In "video" mode the self.drone sends 1280x720 frames.
        In "photo" mode it sends 2592x1936 (952x720) frames.
        The video will always be centered in the window.
        In photo mode, if we keep the window at 1280x720 that gives us ~160px on
        each side for status information, which is ample.
        Video mode is harder because then we need to abandon the 16:9 display size
        if we want to put the HUD next to the video.
        """
        if speed == 0:
            return
        self.drone.set_video_mode(not self.drone.zoom)

    def flight_data_handler(self, event, sender, data):
        """Listener to flight data from the drone."""
        text = str(data)
        if self.prev_flight_data != text:
            self.prev_flight_data = text

    def handle_flight_received(self, event, sender, data):
        """Create a file in ~/Pictures/ to receive image from the drone"""
        path = '%s/Pictures/tello-%s.jpeg' % (
            os.getenv('HOME'),
            datetime.datetime.now().strftime(self.date_fmt))
        with open(path, 'wb') as out_file:
            out_file.write(data)
        print('Saved photo to %s' % path)


if __name__ == '__main__':
    main()
