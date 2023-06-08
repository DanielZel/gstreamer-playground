import os
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('GObject', '2.0')
from gi.repository import GLib, GObject, Gst

assert os.getenv('GST_DEBUG') is None
os.environ['GST_DEBUG'] = '*:ERROR'
Gst.init(None)

RECORDING_LEN_SEC = 5


def location_generator():
    rec_index = 0
    while True:
        yield "out/rec{}.mp4".format(rec_index)
        rec_index += 1


class PipelineData:
    def __init__(self, pipeline, src, main_loop, rec_loc_gen):
        self.pipeline = pipeline
        self.src = src
        self.main_loop = main_loop
        self.loc_gen = rec_loc_gen


def bus_callback(bus, message, data: PipelineData):
    message_type = message.type
    if message_type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("Error: %s" % err, debug)
        data.main_loop.quit()
    return True


def probe_cb(pad, info, pdata: PipelineData):
    bin = pdata.pipeline.get_by_name("encoder_bin")
    bin.send_event(Gst.Event.new_eos())
    peer = pad.get_peer()
    pad.unlink(peer)

    bin.set_state(Gst.State.NULL)
    bin.get_state(Gst.CLOCK_TIME_NONE)
    pdata.pipeline.remove(bin)

    next_file = next(pdata.loc_gen)
    print("next-file: {}".format(next_file))
    encoder_bin, encoder_element = create_encoding_bin(next_file)
    pdata.pipeline.add(encoder_bin)
    pdata.pipeline.get_by_name('queue0').link(encoder_element)
    encoder_bin.sync_state_with_parent()
    GLib.timeout_add_seconds(RECORDING_LEN_SEC, rollover_cb, pdata)

    return Gst.PadProbeReturn.REMOVE


def rollover_cb(pdata: PipelineData):
    queue_src_pad = pdata.pipeline.get_by_name("queue0").get_static_pad('src')
    queue_src_pad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, probe_cb, pdata)
    return GLib.SOURCE_REMOVE


def create_encoding_bin(location):
    enc_bin = Gst.Bin.new('encoder_bin')
    x264enc = Gst.ElementFactory.make('x264enc')
    x264enc.set_property("tune", "zerolatency")
    mp4mux = Gst.ElementFactory.make('mp4mux')
    filesink = Gst.ElementFactory.make('filesink')
    filesink.set_property('location', location)
    filesink.set_property('sync', True)
    enc_bin.add(x264enc)
    enc_bin.add(mp4mux)
    enc_bin.add(filesink)
    x264enc.link(mp4mux)
    mp4mux.link(filesink)
    return enc_bin, x264enc


def main():
    rec_loc_gen = location_generator()
    pipeline = Gst.Pipeline.new()
    src = Gst.ElementFactory.make('videotestsrc')
    capsfilter = Gst.ElementFactory.make('capsfilter', 'capsfilter')
    caps = Gst.caps_from_string(f'video/x-raw,width=640,height=480')
    capsfilter.set_property('caps', caps)
    video_rate = Gst.ElementFactory.make('videorate')
    video_rate.set_property('max-rate', 10)
    time_overlay = Gst.ElementFactory.make('timeoverlay')
    time_overlay.set_property('halignment', 'left')
    time_overlay.set_property('valignment', 'top')
    queue = Gst.ElementFactory.make('queue')

    pipeline.add(src)
    pipeline.add(capsfilter)
    pipeline.add(video_rate)
    pipeline.add(time_overlay)
    pipeline.add(queue)

    first_recording_path = next(rec_loc_gen)
    print("starting with: {}".format(first_recording_path))
    encoder_bin, encoder_element = create_encoding_bin(first_recording_path)
    pipeline.add(encoder_bin)

    src.link(capsfilter)
    capsfilter.link(video_rate)
    video_rate.link(time_overlay)
    time_overlay.link(queue)
    queue.link(encoder_element)

    loop = GLib.MainLoop()
    pdata = PipelineData(pipeline, src, loop, rec_loc_gen)

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_callback, pdata)

    pipeline.set_state(Gst.State.PLAYING)
    GLib.timeout_add_seconds(RECORDING_LEN_SEC, rollover_cb, pdata)
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

    pipeline.set_state(Gst.State.NULL)


if __name__ == '__main__':
    main()
