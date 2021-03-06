# -*- coding: utf-8 -*-
"""
Holds all instrumentation devices.

TO DO:
  Allow probes to catastrophically fail
  Program fail behavior
  
  
drift_sigma refers to drift per year variance

"""
import random

import numpy as np
from quantities import Quantity as Q
import quantities as q

import param, helper_functions


class machine:
  """All machines have a random calibration error.  They then drift until 
  recalibrated.  Placeholder parent class."""

class probe(machine):
  """Parent class of all online probes. Moves towards correct value each step.  
  """

  def __init__(self, cal_reference):
    # Timestep propagation delay ratio
    self.ratio = 1-(1-0.98)**(param.resolution/self.p['t98'])
    self.reference = cal_reference

class scale(machine):
  """Scale.  Very accurate.  Doesn't break, little errors."""
  p = param.instrumentation['Scale']
  def read_value(self, environment, _):
    if param.skip_units:
      random_error = helper_functions.gauss(0, self.p['random_error_sigma'])
    else:
      random_error = helper_functions.gauss(Q(0, 'kg'), self.p['random_error_sigma'])
    mass = environment['mass']+ random_error
    return {'mass': mass}
  
class O2_probe(probe):
  """All errors (except one-point) are introduced as a slope, not offset.
  
  Outputs in %DO saturation."""
  # Slope drift.  <5% every 2 months
  p = param.instrumentation['Probe']['O2']
  
  def __init__(self, time, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.drift_slope = helper_functions.gauss(0, self.p['drift_CV'])
    #Large offset as probe isn't yet calibrated
    self.sys_error = 5
    self.value = 100
    self.one_point(time)  #auto one-point
    self.conversion_constant = (1/Q(0.00217, 'mM')).simplified
    if param.skip_units:
      self.conversion_constant = float(self.conversion_constant)
    
    
  def one_point(self, time, value = 100):
    self.cal_time = time
    self.sys_error = self.reference.read_O2_value(value) - \
      value + helper_functions.gauss(0, self.p['random_CV'])    
  
  def read_value(self, environment, cells):
    #time since last calibration
    time_delta = environment['time'] - self.cal_time
    drift_error = time_delta / np.timedelta64(365, 'D')*self.drift_slope
    random_error = helper_functions.gauss(0, self.p['random_CV'])
    percent_DO = environment['br_molarity']['dO2']*self.conversion_constant
    value = percent_DO*(1+drift_error+random_error)+self.sys_error
    self.value = self.ratio*value+(1-self.ratio)*self.value
    return {'dO2': self.value}
    
  
class pH_probe(probe):
  """pH is a log scale; any error in the slope expresses itself as a net error.
  """
  # Net drift: < 0.1 pH/week
  p = param.instrumentation['Probe']['pH']
  
  def __init__(self, time, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.drift_slope = helper_functions.gauss(0, self.p['drift_sigma'])
    #Large offset as probe isn't yet calibrated
    self.sys_error = 5
    self.value = 7
    self.one_point(time)  #auto one-point
    
  def one_point(self, time, value = 7):
    """Calibrate the probe according to the reference."""
    self.cal_time = time
    self.sys_error = self.reference.read_pH_value(value) - \
      value + helper_functions.gauss(0, self.p['random_sigma'])    
  
  def read_value(self, environment, cells):
    # time_delta is time since last calibration
    time_delta = environment['time'] - self.cal_time
    drift_error = time_delta / np.timedelta64(365, 'D')*self.drift_slope
    random_error = helper_functions.gauss(0, self.p['random_sigma'])
    value = environment['pH']+drift_error+random_error+self.sys_error
    self.value = self.ratio*value+(1-self.ratio)*self.value
    return {'pH': self.value}
  
class temperature_probe(machine):
  """Temperature probes are both reliable and accurate.  
  
  Assumed no drift.
  """
  # Net drift: < 0.1 pH/week
  p = param.instrumentation['Probe']['temperature']
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    #Large offset as probe isn't yet calibrated
    self.sys_error = helper_functions.gauss(0, self.p['systematic_sigma'])
    self.value = 30
    self.ratio = 1-(1-0.98)**(param.resolution/self.p['t98'])
    
  
  def read_value(self, environment, cells):
    # time_delta is time since last calibration
    random_error = helper_functions.gauss(0, self.p['random_sigma'])
    value = environment['temperature']+self.sys_error+random_error
    self.value = self.ratio*value+(1-self.ratio)*self.value
    return {'temperature': self.value}
    
class BGA(machine):
  """BGA have very high drift, and as a result are designed to constantly 
  self-calibrate.  Therefor, we assume there is no drift error and instead have 
  only random error.
  
  Used both to calibrate probes (with read_XX_value method) as well as take
  offline measurements."""
  p = param.instrumentation['BGA']
  
  def __init__(self):
    self.O2_systematic_error = helper_functions.gauss(0, self.p['O2_systematic_error_CV'])
    self.CO2_systematic_error = helper_functions.gauss(0, self.p['CO2_systematic_error_CV'])
    self.pH_systematic_error = helper_functions.gauss(0, self.p['pH_systematic_error_sigma'])
    
  def read_O2_value(self, value):
    random_error = helper_functions.gauss(0, self.p['O2_random_error_CV'])
    return value * (1+ random_error + self.O2_systematic_error)
  
  def read_CO2_value(self, value):
    random_error = helper_functions.gauss(0, self.p['CO2_random_error_CV'])
    return value * (1+ random_error + self.CO2_systematic_error)
    
  def read_pH_value(self, value):
    random_error = helper_functions.gauss(0, self.p['pH_random_error_sigma'])
    return value + random_error + self.pH_systematic_error
  
  def read_value(self, environment, cells):
    """For BGA usage as part of offline assays."""
    # offline assay, so don't need to specify ['bioreactor']
    O2 = self.read_O2_value(environment['dO2'])
    pH = self.read_pH_value(environment['pH'])
    # Mole fraction is ~0.9756 for CO2 of total inorganic carbon
    CO2 = self.read_CO2_value(environment['dCO2'])
    return {'BGA_dO2': O2, 'BGA_pH': pH, 'BGA_dCO2': CO2}

    
class bioHT(machine):
  """Performs various assays.  Takes tests to perform as argument."""
  p = param.instrumentation['bioHT']
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    available_assays = ['glucose', 'IGG', 'ammonia', 'glutamine', 'iron']
    self.sys_error = {}
    #Create systematic errors for each assay
    for assay in available_assays:
      self.sys_error[assay] = helper_functions.gauss(0, self.p['systematic_error_CV'])
    self.error_CV = lambda assay: (
      1+helper_functions.gauss(0, self.p['random_error_CV'])+self.sys_error[assay]) 
    
  def read_value(self, assay, env, cells):
    if assay == 'IGG':
      value = env['IGG_a']+env['IGG_b']+env['IGG_n']
    else: value = env[assay]
    
    return {assay: value*self.error_CV(assay)*param.molecular_weight[assay]}


class cell_counter(machine):
  """No drift implemented, as was not able to find any figures for this."""
  p = param.instrumentation['Cell_Counter']
  
  def __init__(self, **kwargs):
    super(cell_counter, self).__init__(**kwargs)
    self.update_calibration()

  def update_calibration(self):
    self.density_sys_error = helper_functions.gauss(0, self.p['density_systematic_error_CV'])
    self.via_sys_error = helper_functions.gauss(0, self.p['viability_systematic_error_sigma'])
    if param.skip_units:
      self.size_sys_error = helper_functions.gauss(0, self.p['size_systematic_error_sigma'])
    else:
      self.size_sys_error = helper_functions.gauss(Q(0, 'm'), self.p['size_systematic_error_sigma'])
      
    
  def read_value(self, env, cells):
    # time_delta is time since last calibration
    random_error = helper_functions.gauss(0, self.p['density_random_error_CV'])
    VCD = cells['living_cells'] /env['volume']
    VCD *=(1+random_error+self.density_sys_error)
    
    if param.skip_units:
      random_error = helper_functions.gauss(0, self.p['size_random_error_sigma'])
    else:
      random_error = helper_functions.gauss(Q(0,'m'), self.p['size_random_error_sigma'])
    cell_size = cells['diameter']+self.size_sys_error+random_error
    
    random_error = helper_functions.gauss(0, self.p['viability_random_error_sigma'])
    viability = cells['living_cells']/cells['total_cells']
    error_frac = random_error+self.via_sys_error
    if error_frac > 0:
      viability = (error_frac+viability*(1-error_frac))
    else:
      viability *= 1+error_frac
    return {'VCD': VCD, 'cell_diameter': cell_size, 'viability': viability}

class osmo(machine):
  """Temperature probes are both reliable and accurate.  
  
  Assumed no drift.
  """
  # Net drift: < 0.1 pH/week
  p = param.instrumentation['Osmo']
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    #Large offset as probe isn't yet calibrated
    self.units = Q(1, 'mol/m**3')
    if param.skip_units:
      self.units = 1
    self.sys_error = helper_functions.gauss(0, self.p['systematic_sigma'])*self.units
  
  def read_value(self, environment, cells):
    # time_delta is time since last calibration
    random_error = helper_functions.gauss(0, self.p['random_sigma'])*self.units
    value = environment['mOsm']+self.sys_error+random_error
    return {'mOsm': value}

class flowmeter:
  p = param.instrumentation['flowmeter']
  """Levitronix flowmeter using doppler."""
  def __init__(self):
    if param.skip_units:
      self.systematic_error = helper_functions.gauss(
        0, self.p['systematic_sigma'])
    else:
      self.systematic_error = helper_functions.gauss(
        Q(0, 'm**3/s'), self.p['systematic_sigma'])
    
  def read_value(self, env, cells):
    value = env['recirc_rate']
    random_error = helper_functions.gauss(1, self.p['random_CV'])
    return {'recirc_rate':random_error * (value + self.systematic_error)}
  
class levitronix_RPM_meter:
  """Measures RPM of levitronix pump."""
  p = param.instrumentation['levitronix_RPM']
  def __init__(self):
    if param.skip_units:
      self.systematic_error = helper_functions.gauss(
        0, self.p['systematic_sigma'])
    else:
      self.systematic_error = helper_functions.gauss(
        Q(0, '1/s'), self.p['systematic_sigma'])
    
  def read_value(self, env, cells):
    value = env['recirc_RPM']
    random_error = helper_functions.gauss(1, self.p['random_CV'])
    return {'recirc_RPM':random_error * (value + self.systematic_error)}
  
    
  
class wrapper:
  """Main class that performs all the assays."""
  def __init__(self, start_time, osmo, BGA_instance, cell_counter,  bioHT=None,
               bioHT_list=None, pH = True, O2 = True, temp = True,
               use_scale = True, recirc_flowmeter = False, levitronix_RPM = False):
    """Experimental_setup should take the form of:
      BGA: instance of BGA to calibrate against
      bioHT: instance of bioHT
      cell_counter: instance of cell_counter
      
      bioHT_list: list of bool for assays to run (see bioHT).  None for no bioHT
      pH: bool
      O2: bool
      temp: bool
      use_scale: bool
      recirc_flowmeter: bool
      levitronix_RPM: bool
      )
    """
    self.online_assays = []
    self.offline_assays = [BGA_instance.read_value]
    for assay in bioHT_list:
      if bioHT == None:
        raise ValueError('Need instance of bioHT to run assays!')
      self.offline_assays.append(lambda env, cell, assay = assay:bioHT.read_value(assay, env, cell))
    if cell_counter != None: self.offline_assays.append(cell_counter.read_value)
    if osmo != None: self.offline_assays.append(osmo.read_value)
    if pH: self.online_assays.append(pH_probe(start_time, BGA_instance).read_value)
    if O2: self.online_assays.append(O2_probe(start_time, BGA_instance).read_value)
    if temp: self.online_assays.append(temperature_probe().read_value)
    if use_scale: self.online_assays.append(scale().read_value)
    if recirc_flowmeter: self.online_assays.append(flowmeter().read_value)
    if levitronix_RPM: self.online_assays.append(levitronix_RPM_meter().read_value)
    
  def step(self, environment, cells, offline):
    """Takes state of cells and environment and outputs assays.  
    Inputs:
      environment: dict output from environment
      cells: dict output from cells
      offline: bool, whether to perform offline assays
      """
    results={'time':environment['time']}
    for assay in self.online_assays:
      results.update(assay(environment, cells))
    if offline:
      if 'permeate_molarity' in environment:
        # perfusion mode
        permeate = {}
        mixture = environment['permeate_molarity']
        mixture['pH'] = environment['pH']
        mixture['volume'] = environment['volume']
        for assay in self.offline_assays:
          if not type(assay) == type(cell_counter):
            permeate.update(assay(mixture, cells))
        results['permeate'] = permeate
      br = {}
      mixture = environment['br_molarity']
      mixture['pH'] = environment['pH']
      mixture['volume'] = environment['volume']
      for assay in self.offline_assays:
        br.update(assay(mixture, cells))
      results['bioreactor'] = br
    return results


    
  
if __name__ == '__main__':
  tests.assays_test()
  
