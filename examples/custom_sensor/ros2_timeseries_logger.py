#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, numbers, time
from pathlib import Path
from typing import Any
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy,HistoryPolicy,QoSProfile,ReliabilityPolicy
from rosidl_runtime_py.utilities import get_message

def stamp_to_ns(stamp):
    if stamp is None or not hasattr(stamp,'sec') or not hasattr(stamp,'nanosec'): return None
    sec=int(stamp.sec); ns=int(stamp.nanosec); return None if (sec==0 and ns==0) else sec*1_000_000_000+ns

def source_timestamp_ns(msg):
    h=getattr(msg,'header',None); return stamp_to_ns(getattr(h,'stamp',None)) if h is not None else None

def flatten_numeric(value:Any,prefix:str='',out=None):
    if out is None: out={}
    if isinstance(value,bool): out[prefix]=bool(value); return out
    if isinstance(value,numbers.Real): out[prefix]=float(value); return out
    if isinstance(value,(list,tuple)) and all(isinstance(x,numbers.Real) for x in value): out[prefix]=[float(x) for x in value]; return out
    gf=getattr(value,'get_fields_and_field_types',None)
    if callable(gf):
        for name in gf():
            if name=='header': continue
            child=getattr(value,name); flatten_numeric(child,f'{prefix}.{name}' if prefix else name,out)
    return out

class TimeSeriesLogger(Node):
    def __init__(self,topic,msg_type_name,sensor_id,output,duration_s,reliability,flush_interval_s):
        super().__init__('generic_timeseries_logger'); self.output=output.expanduser().resolve(); self.output.parent.mkdir(parents=True,exist_ok=True); self.sensor_id=sensor_id; self._file=self.output.open('w',encoding='utf-8'); self._buffer=[]; self._sample_index=0; self._start_ns=time.monotonic_ns(); self._finished=False
        rel=ReliabilityPolicy.RELIABLE if reliability=='reliable' else ReliabilityPolicy.BEST_EFFORT; qos=QoSProfile(history=HistoryPolicy.KEEP_LAST,depth=4096,reliability=rel,durability=DurabilityPolicy.VOLATILE)
        self._sub=self.create_subscription(get_message(msg_type_name),topic,self._callback,qos); self._flush_timer=self.create_timer(max(flush_interval_s,0.05),self.flush); self._duration_timer=self.create_timer(duration_s,self.finish) if duration_s>0 else None
        meta={'format_version':1,'topic':topic,'msg_type':msg_type_name,'sensor_id':sensor_id,'receive_clock':'CLOCK_MONOTONIC via time.monotonic_ns()','wall_clock':'CLOCK_REALTIME via time.time_ns()','qos_reliability':reliability,'note':'receive_monotonic_ns is callback-entry time on this host; source_timestamp_ns semantics depend on publisher header.stamp.'}
        with self.output.with_suffix(self.output.suffix+'.meta.json').open('w',encoding='utf-8') as f: json.dump(meta,f,indent=2); f.write('\n')
        self.get_logger().info(f'Logging {msg_type_name} {topic} -> {self.output}')
    @property
    def finished(self): return self._finished
    def _callback(self,msg):
        if self._finished: return
        mono=time.monotonic_ns(); wall=time.time_ns(); self._buffer.append({'sample_index':self._sample_index,'sensor_id':self.sensor_id,'source_timestamp_ns':source_timestamp_ns(msg),'receive_wall_ns':wall,'receive_monotonic_ns':mono,'elapsed_s':(mono-self._start_ns)/1e9,'values':flatten_numeric(msg)}); self._sample_index+=1
    def flush(self):
        if not self._buffer: return
        for r in self._buffer: self._file.write(json.dumps(r,separators=(',',':'))+'\n')
        self._buffer.clear(); self._file.flush()
    def finish(self):
        if self._finished: return
        self._finished=True; self.flush(); self._flush_timer.cancel();
        if self._duration_timer is not None: self._duration_timer.cancel()
        self.get_logger().info(f'Finished: {self._sample_index} samples -> {self.output}')
    def close(self): self.finish(); self._file.close() if not self._file.closed else None

def parse_args():
    p=argparse.ArgumentParser(); p.add_argument('--topic',required=True); p.add_argument('--msg-type',required=True); p.add_argument('--sensor-id',default='external_sensor'); p.add_argument('--output',type=Path,required=True); p.add_argument('--duration',type=float,default=0.0); p.add_argument('--qos-reliability',choices=('best_effort','reliable'),default='best_effort'); p.add_argument('--flush-interval',type=float,default=0.5); return p.parse_known_args()
def main():
    a,ros_args=parse_args(); rclpy.init(args=ros_args); n=TimeSeriesLogger(a.topic,a.msg_type,a.sensor_id,a.output,a.duration,a.qos_reliability,a.flush_interval)
    try:
        while rclpy.ok() and not n.finished: rclpy.spin_once(n,timeout_sec=0.1)
    except KeyboardInterrupt: pass
    finally:
        n.close(); n.destroy_node();
        if rclpy.ok(): rclpy.shutdown()
if __name__=='__main__': main()
