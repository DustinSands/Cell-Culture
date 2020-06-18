# -*- coding: utf-8 -*-
"""
Holds all physical actuation equipment.  Takes a setpoint and outputs actual
quantities.
"""
import random

from quantities import Quantity as Q

class MFC:
  """Takes setpoint and returns actual amount dispensed.  Includes constant 
  systematic error and random error.  Both are minimal.
  
  In: Volumetric flowrate
  Out: Volumetric flowrate"""
  def __init__(self, self_correcting = False, normal_error = 0.005, break_chance = 
               Q(0.1, '/yr')):
    self.error = random.gauss(1, normal_error)
    # 1 = working fine, 0 = broken
    self.broken_mult
    
  def get_amount(self, set_point):
    # Only called if pump is on.  Constant chance of breaking whenever
    # the pump is on.
    if random.random()<float(break_chance*param.resolution):
      self.broken_mult = 0
    return self.error * set_point * self.broken_mult

class peristaltic:
  """Takes the setpoint and returns actual amount dispensed.  Includes error
  in pump calibration (Default: sigma 3%) as well as any self-correcting measures. 
  
  Includes chance to break. (Default: 1/yr)"""
  def __init__(self, self_correcting = False, normal_error = 0.03, break_chance = 
               Q(1, '/yr')):
    self.error = random.gauss(1, normal_error)
    # 1 = working fine, 0 = broken
    self.broken_mult
    
  def get_amount(self, set_point):
    # Only called if pump is on.  Constant chance of breaking whenever
    # the pump is on.
    if random.random()<float(break_chance*param.resolution):
      self.broken_mult = 0
    return self.error * set_point * self.broken_mult
  
# class scale:
#   """A scale.  Assumes you're using it within range.  These things are pretty
#   reliable and accurate, so no sources of error introduced here."""

class wrapper:
  
  def __init__(self, equipment_configuration):
    pass    