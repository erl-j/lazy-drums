#%%
from playback_engine import PlaybackEngine
import BEATS
        
playback_engine = PlaybackEngine(ppq=96)
# # show rock beat

#seq, nq = playback_engine.loop_sequence(BEATS.ROCK_BEAT)

beat = BEATS.PROG_BEAT
beat = playback_engine.loop_beat(beat, n_loops=2)
beat["tempo"] = 170
playback_engine.show_beat(beat)
audio = playback_engine.play_beat(beat, n_loops=1, autoplay=False)

# %%
