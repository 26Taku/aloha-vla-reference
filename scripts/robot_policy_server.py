"""Run the fixed LeRobot async server; this process never connects to a robot."""
import functools
import runpy
import sys
from lerobot.async_inference import helpers

helpers.observations_similar = functools.partial(helpers.observations_similar, atol=0.01)
print('Observation similarity tolerance: 0.01', flush=True)
sys.argv = ['policy_server', '--host=127.0.0.1', '--port=8080', '--fps=30']
runpy.run_module('lerobot.async_inference.policy_server', run_name='__main__')
