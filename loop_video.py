import os
import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib


START_SEC = 0

assert os.getenv('GST_DEBUG') is None
os.environ['GST_DEBUG'] = '*:ERROR'

Gst.init(None)


class PipelineData:
    def __init__(self, start_second, pipeline, main_loop):
        self.start_second = start_second
        self.pipeline = pipeline
        self.main_loop = main_loop


def bus_callback(bus, message, data: PipelineData):
    message_type = message.type
    if message_type == Gst.MessageType.EOS:
        print("end-of-stream reached")
        data.main_loop.quit()
    elif message_type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("error: %s" % err, debug)
        data.main_loop.quit()
    elif message_type == Gst.MessageType.SEGMENT_DONE:
        data.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.SEGMENT,  Gst.SECOND * data.start_second)

    data.pipeline.set_state(Gst.State.PLAYING)
    return True


def video_loop():
    loop = GLib.MainLoop()

    pipeline = Gst.parse_launch("filesrc location=test.mp4 ! decodebin ! autovideosink")
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_callback, PipelineData(start_second=START_SEC, pipeline=pipeline, main_loop=loop))
    pipeline.set_state(Gst.State.PLAYING)
    pipeline.get_state(Gst.CLOCK_TIME_NONE)
    pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.SEGMENT, Gst.SECOND * START_SEC)

    try:
        loop.run()
    except KeyboardInterrupt:
        pass

    print("shutting the pipeline down...")
    pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    video_loop()
