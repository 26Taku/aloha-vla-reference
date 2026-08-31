#!/usr/bin/env python3
from __future__ import annotations
import json, logging, time
from pathlib import Path
from typing import Any
import lerobot.scripts.lerobot_record as upstream

class FrameTimestampWriter:
    def __init__(self, dataset: Any, fps: int) -> None:
        self.episode_index=int(dataset.num_episodes); self.fps=int(fps); self._frame_index=0
        root=Path(dataset.root).expanduser().resolve(); d=root/'meta'/'frame_timestamps'; d.mkdir(parents=True, exist_ok=True)
        self.path=d/f'episode_{self.episode_index:06d}.jsonl'; self._file=self.path.open('w',encoding='utf-8')
        meta={'format_version':1,'clock':'CLOCK_MONOTONIC via time.monotonic_ns()','wall_clock':'CLOCK_REALTIME via time.time_ns()','episode_index':self.episode_index,'fps':self.fps,'representative_robot_time':'observation_end_monotonic_ns','note':'Software timestamps around robot.get_observation(), robot.send_action(), and dataset.add_frame(); not hardware-trigger or camera-exposure timestamps.'}
        with (d/f'episode_{self.episode_index:06d}.meta.json').open('w',encoding='utf-8') as f: json.dump(meta,f,indent=2); f.write('\n')
        logging.info('Frame timestamp sidecar: %s', self.path)
    def write(self, rec):
        rec={'episode_index':self.episode_index,'frame_index':self._frame_index,'dataset_timestamp_s':self._frame_index/self.fps,**rec}
        self._file.write(json.dumps(rec,separators=(',',':'))+'\n'); self._frame_index+=1
        if self._frame_index % self.fps == 0: self._file.flush()
    def close(self):
        if not self._file.closed: self._file.flush(); self._file.close()

@upstream.safe_stop_image_writer
def record_loop_with_timestamps(robot, events: dict, fps: int, teleop_action_processor, robot_action_processor, robot_observation_processor, dataset=None, teleop=None, control_time_s: int|None=None, single_task: str|None=None, display_data: bool=False, display_mode: str='rerun', display_compressed_images: bool=False):
    if dataset is not None and dataset.fps != fps: raise ValueError(f'The dataset fps should be equal to requested fps ({dataset.fps} != {fps}).')
    teleop_arm=teleop_keyboard=None
    if isinstance(teleop,list):
        teleop_keyboard=next((t for t in teleop if isinstance(t,upstream.KeyboardTeleop)),None)
        teleop_arm=next((t for t in teleop if isinstance(t,(upstream.so_leader.SO100Leader|upstream.so_leader.SO101Leader|upstream.koch_leader.KochLeader|upstream.omx_leader.OmxLeader))),None)
        if not (teleop_arm and teleop_keyboard and len(teleop)==2 and robot.name=='lekiwi_client'): raise ValueError('For multi-teleop, the list must contain exactly one KeyboardTeleop and one arm teleoperator. Currently only supported for LeKiwi robot.')
    control_interval=1/fps; no_action_count=0; timestamp=0; start_episode_t=time.perf_counter(); writer=FrameTimestampWriter(dataset,fps) if dataset is not None else None
    try:
        while timestamp < control_time_s:
            start_loop_t=time.perf_counter(); loop_start_ns=time.monotonic_ns()
            if events['exit_early']: events['exit_early']=False; break
            obs_start_ns=time.monotonic_ns(); obs=robot.get_observation(); obs_end_ns=time.monotonic_ns(); obs_end_wall_ns=time.time_ns()
            obs_processed=robot_observation_processor(obs)
            if dataset is not None: observation_frame=upstream.build_dataset_frame(dataset.features,obs_processed,prefix=upstream.OBS_STR)
            if isinstance(teleop,upstream.Teleoperator):
                act=teleop.get_action()
                if robot.name=='unitree_g1': teleop.send_feedback(obs)
                act_processed_teleop=teleop_action_processor((act,obs)); action_values=act_processed_teleop; robot_action_to_send=robot_action_processor((act_processed_teleop,obs))
            elif isinstance(teleop,list):
                arm_action={f'arm_{k}':v for k,v in teleop_arm.get_action().items()}; keyboard_action=teleop_keyboard.get_action(); base_action=robot._from_keyboard_to_base_action(keyboard_action); act={**arm_action,**base_action} if base_action else arm_action
                act_processed_teleop=teleop_action_processor((act,obs)); action_values=act_processed_teleop; robot_action_to_send=robot_action_processor((act_processed_teleop,obs))
            else:
                no_action_count+=1
                if no_action_count==1 or no_action_count%10==0: logging.warning('No teleoperator provided, skipping action generation.')
                continue
            _sent_action=robot.send_action(robot_action_to_send); action_sent_ns=time.monotonic_ns()
            if dataset is not None:
                action_frame=upstream.build_dataset_frame(dataset.features,action_values,prefix=upstream.ACTION); frame={**observation_frame,**action_frame,'task':single_task}; dataset.add_frame(frame); frame_added_ns=time.monotonic_ns()
                writer.write({'loop_start_monotonic_ns':loop_start_ns,'observation_start_monotonic_ns':obs_start_ns,'observation_end_monotonic_ns':obs_end_ns,'observation_end_wall_ns':obs_end_wall_ns,'action_sent_monotonic_ns':action_sent_ns,'frame_added_monotonic_ns':frame_added_ns,'observation_duration_ns':obs_end_ns-obs_start_ns})
            if display_data: upstream.log_visualization_data(display_mode,observation=obs_processed,action=action_values,compress_images=display_compressed_images)
            dt_s=time.perf_counter()-start_loop_t; sleep_time_s=control_interval-dt_s
            if sleep_time_s<0: logging.warning(f'Record loop is running slower ({1/dt_s:.1f} Hz) than target FPS ({fps} Hz).')
            upstream.precise_sleep(max(sleep_time_s,0.0)); timestamp=time.perf_counter()-start_episode_t
    finally:
        if writer is not None: writer.close()

def main():
    upstream.record_loop=record_loop_with_timestamps; upstream.main()
if __name__=='__main__': main()
