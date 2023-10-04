#%%
import pedalboard
import json
from CONSTANTS import NR_TO_DRUM_NAME
import pydash
import itertools
import numpy as np
import IPython.display as ipd
import os
import matplotlib.pyplot as plt
import BEATS

def play_audio(audio,sr, autoplay=False):
    ipd.display(ipd.Audio(audio, rate=sr, autoplay=autoplay))

class PlaybackEngine:

    def __init__(self, ppq) -> None:
        
        self.NR_TO_DRUM_NAME = NR_TO_DRUM_NAME
        self.DRUM_NAME_TO_NR = {v: k for k, v in NR_TO_DRUM_NAME.items()}

        self.ppq = ppq
        self.sample_rate = 44_100
        self.n_gm_drums = 81
        self.DRUM_NAME_TO_SAMPLES = {
            drum_name
            : self.load_sample(f"GM_samples/{drum_name}.wav") for drum_name in self.DRUM_NAME_TO_NR.keys()
        }
        self.CHOKE_GROUP_2_DRUM_NAMES = {
            "hi_hat": ["Closed Hi Hat", "Open Hi-Hat"],
        }
        self.DRUM_NAME_TO_CHOKE_GROUP = { drum_name: choke_group for choke_group, drum_names in self.CHOKE_GROUP_2_DRUM_NAMES.items() for drum_name in drum_names}
        # for drums not in a choke group, they are their own choke group. add them to both dicts
        for drum_name in self.DRUM_NAME_TO_NR.keys():
            if drum_name not in self.DRUM_NAME_TO_CHOKE_GROUP.keys():
                self.DRUM_NAME_TO_CHOKE_GROUP[drum_name] = drum_name
                self.CHOKE_GROUP_2_DRUM_NAMES[drum_name] = [drum_name]
    

    def load_sample(self, sample_path):
        # load audio with pedalboard
        try:
            with pedalboard.io.AudioFile(sample_path).resampled_to(self.sample_rate) as f:
                return self.make_stereo(f.read(int(f.samplerate * f.duration)))
        except:
            print(f"Error loading sample {sample_path}")
            return None
    def make_stereo(self, sample):
        # stack sample on top of itself to make stereo
        return np.vstack((sample, sample))

    def render_beat(self, beat, n_loops):
        """Plays drums

        Args:
            sequence (list): A list of {drum_name, time, velocity} dicts
            tempo (int) : Tempo in BPM
        """        
        beat = beat.copy()
        sequence = beat["sequence"]
        tempo = beat["tempo"]
        time_signature = beat["time_signature"]
        n_bars = beat["n_bars"]

        counts_per_bar = time_signature[0]
        counted_unit = time_signature[1]
        counted_unit_ticks = 4 * self.ppq // counted_unit

        max_tick = int(n_bars * counts_per_bar * counted_unit_ticks)

        # deep copy sequence so we don't modify original
        sequence = [event.copy() for event in sequence]

        # loop sequence
        #sequence, n_quarters = self.loop_sequence(sequence, n_quarters, n_loops)

        # sort sequence by time
        sequence = sorted(sequence, key=lambda x: x["onset"])

        # group hits by choke group
        # if a drum is not in a choke group, it is its own choke group
        choke_groups = {choke_group: [] for choke_group in self.CHOKE_GROUP_2_DRUM_NAMES.keys()}
        for event in sequence:
            choke_groups[self.DRUM_NAME_TO_CHOKE_GROUP[event["drum_name"]]].append(event)
        # remove empty choke groups
        choke_groups = {choke_group: events for choke_group, events in choke_groups.items() if len(events) > 0}

        audio_duration = max_tick * 60 / (tempo * self.ppq)
        audio = np.zeros((2,(int(audio_duration * self.sample_rate))))

        for choke_group, events in choke_groups.items():
            choke_group_audio = np.zeros_like(audio)
            for hit in events:
                sample = self.DRUM_NAME_TO_SAMPLES[hit["drum_name"]]
                sample_length = sample.shape[-1]
                start_time = hit["onset"] * 60 / (tempo * self.ppq)
                start_sample = int(start_time * self.sample_rate)
                assert start_sample <= choke_group_audio.shape[1]
                end_sample = start_sample + sample_length
                end_sample = min(end_sample-1, audio.shape[1])
                active_length = end_sample - start_sample
                choke_group_audio[:,start_sample:end_sample] = sample[:,:active_length] * hit["velocity"] / 127
            audio += choke_group_audio
        return audio
    
    def loop_beat(self, beat, n_loops):
        """Loops a sequence

        Args:
            sequence (list): A list of {drum_name, time, velocity} dicts
            n_quarters (int): Number of quarters in a loop
            n_loops (int): Number of loops
        """        
        # deep copy beat so we don't modify original
        beat = beat.copy()

        sequence = beat["sequence"]
        time_signature = beat["time_signature"]
        n_bars = beat["n_bars"]

        counts_per_bar = time_signature[0]
        counted_unit = time_signature[1]
        counted_unit_ticks = 4 * self.ppq // counted_unit

        max_tick = int(n_bars * counts_per_bar * counted_unit_ticks)

        sequence = beat["sequence"]
        # deep copy sequence so we don't modify original
        sequence = [event.copy() for event in sequence]

        ticks_per_loop = max_tick

        new_sequence = []
        for i in range(n_loops):
            for event in sequence:
                new_event = event.copy()
                new_event["onset"] += i * ticks_per_loop
                new_sequence.append(new_event)
        beat["sequence"] = new_sequence
        beat["n_bars"] = n_bars * n_loops
        return beat
    
    def clean_up_beat(self, beat):
        # deep copy beat so we don't modify original
        beat = beat.copy()
        sequence = beat["sequence"]
        tempo = beat["tempo"]
        time_signature = beat["time_signature"]
        n_bars = beat["n_bars"]

        counts_per_bar = time_signature[0]
        counted_unit = time_signature[1]
        counted_unit_ticks = 4 * self.ppq // counted_unit
        max_tick = int(n_bars * counts_per_bar * counted_unit_ticks)

        new_sequence = []
        # filter out violations
        for event in sequence:
            # onsets
            if event["onset"] >= 0 and event["onset"] <= max_tick:
                if event["velocity"] >= 1 and event["velocity"] <= 127:
                    if event["drum_name"] in self.DRUM_NAME_TO_NR.keys():
                        new_sequence.append(event)
            
        beat["sequence"] = new_sequence
        return beat


    def validate_beat(self, beat):
        beat = beat.copy()
        sequence = beat["sequence"]
        tempo = beat["tempo"]
        time_signature = beat["time_signature"]
        n_bars = beat["n_bars"]

        counts_per_bar = time_signature[0]
        counted_unit = time_signature[1]
        counted_unit_ticks = 4 * self.ppq // counted_unit
        max_tick = int(n_bars * counts_per_bar * counted_unit_ticks)

        # check that all velocities are in range
        for event in sequence:
            assert event["velocity"] >= 1 and event["velocity"] <= 127, f"event {event} has velocity {event['velocity']} outside range 1-127"
        # check that all onsets are in range
        for event in sequence:
            assert event["onset"] >= 0 and event["onset"] <= max_tick, f"event {event} has onset {event['onset']} outside range 0-{max_tick}"
        # assert that all drum names are valid
        for event in sequence:
            assert event["drum_name"] in self.DRUM_NAME_TO_NR.keys(), f"event {event} has drum_name {event['drum_name']} which is not a valid drum name"
        
    
    def play_beat(self, beat, n_loops=1, autoplay=False):
        audio = self.render_beat(beat, n_loops)
        play_audio(audio,self.sample_rate, autoplay=autoplay)
    
    def show_beat(self, beat):
        beat = beat.copy()
        sequence = beat["sequence"]
        tempo = beat["tempo"]
        time_signature = beat["time_signature"]
        n_bars = beat["n_bars"]

        counts_per_bar = time_signature[0]
        counted_unit = time_signature[1]
        counted_unit_ticks = 4 * self.ppq // counted_unit
        
        # make sure we are not modifying the original sequence
        sequence = [event.copy() for event in sequence]
        # add midi note number to each event
        drum_sequence = []
        for event in sequence:
            event["drum_nr"] = self.DRUM_NAME_TO_NR[event["drum_name"]]
            drum_sequence.append(event)

        max_tick = int(n_bars * counts_per_bar * counted_unit_ticks)
        fig, ax = plt.subplots()
        min_nr = min([event["drum_nr"] for event in drum_sequence])
        max_nr = max([event["drum_nr"] for event in drum_sequence])
        ax.set_yticks([event["drum_nr"] for event in drum_sequence])
        ax.set_yticklabels([event["drum_name"] for event in drum_sequence])
        ax.set_xlabel("time")
        ax.set_ylabel("drum")
        ax.set_title(f"n_bars: {n_bars}, time_signature: {time_signature}, tempo: {tempo}")
        ax.set_xlim(0, max_tick)
        ax.set_ylim(min_nr - 1, max_nr + 1)
        # show quarters on x axis
        ax.set_xticks(np.arange(0, max_tick, counted_unit_ticks))
        # put grid lines on quarters
        ax.grid(which="major", axis="x")
        for event in drum_sequence:
            ax.scatter(event["onset"], event["drum_nr"], alpha=event["velocity"]/127, c="black")
        plt.show()
# %%