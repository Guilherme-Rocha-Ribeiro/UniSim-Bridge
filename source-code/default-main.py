# -*- coding: utf-8 -*-
# Standard library
import os 
import sys
import time
import traceback
import numpy as np

# Setting path for local modules 
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

# Local modules
from UnisimConnector import SimulationConnector
import setup_subsep



def main():
    
# =============================================================================
# SIMULATION CONFIG
# =============================================================================
    OUTPUT_FOLDER = os.path.join(script_dir, 'folder_name')
    DB_NAME = os.path.join(script_dir, 'db_name1.db')
    SIMULATION_TAG = 'teste'

    # Simulation control
    # Para continuar uma simulação anterior:
    # 1 - executar primeira Simulação com continue_simulation = False e save_simulation = True
    # 2 - executar segunda Simulação com continue_simulation = True e save_simulation = True
    
    CONTINUE_SIMULATION = False    # Resume from last saved state if True  
    SAVE_SIMULATION = False        # Save last simulation state to .usc file when finished 
    SHOW_INTERFACE = True          # Display UniSim GUI during execution
    EXPORT_CSV = False             # Export the data to csv file
    OVERWRITE = False
    # Initialize simulation
    Simulation = SimulationConnector(setup_subsep.path_unisim, OUTPUT_FOLDER, SIMULATION_TAG, DB_NAME, CONTINUE_SIMULATION, SHOW_INTERFACE)

    Simulation.easy_setup(
            pumps=setup_subsep.PUMPS,
            valves=setup_subsep.VALVES,
            flashtanks=setup_subsep.FLASHTANKS,
            compressors=setup_subsep.COMPRESSORS,
            controllers=setup_subsep.CONTROLLERS,
            heat_exchangers=setup_subsep.HEAT_EXCHANGERS,
            material_streams=setup_subsep.MATERIAL_STREAMS,
            material_streams_phase=setup_subsep.MATERIAL_STREAMS_PHASE,
            heaters=setup_subsep.HEATERS,
            coolers=setup_subsep.COOLERS,
            pipes=setup_subsep.PIPES,
            spreadsheets=setup_subsep.SPREADSHEETS,
        )

    # =============================================================================
    # Setup new properties not in Deafult
    # =============================================================================

    # Simulation.material_streams.properties = {'Temperature':'K'}
    # Simulation.valves.properties = {}
    Simulation.controllers.properties = {'Td': 'seconds', 'Ti': 'seconds', 'Gain': ''}
    # Simulation.compressors.properties = {}
    # Heat exchangers
    Simulation.heat_exchangers.properties = {'Lmtd': 'C',
                                             'ShellHeatTransferCoef': 'kJ/h-m2-C', 'TubeHeatTransferCoef': 'kJ/h-m2-C',
                                             'TubeSidePressureDrop':'bar', 'ShellSidePressureDrop':'bar',
                                             'UA':'kJ/C-h'}
    
    # Build simulation objects
    print("Initializing build_objects()")
    try:
        start = time.time()
        Simulation.build_objects(setup_subsep.SUBFLOWSHEETS)
        end = time.time()
        print(f"Build worked successfully {(end - start):.6f}")
    except Exception as e:
        print(f"Initialization failed: {str(e)}")
        traceback.print_exc()
        return
    
    # =============================================================================
    # Simulation Parameters
    # =============================================================================

    """
    Sample time has a lower limit of 2 seconds (0.033 min, approximately)
    Any smaller values will be automatically reset to 0.033 min.
    """
    TIME_STEP_SIZE = 0.033      # Duration of each simulation time step
    TIME_STEP_UNIT = 'minutes'  # Time unit for step duration ('seconds', 'minutes')
    N_SIM_STEPS = 2000          # Total number of time steps to simulate

    # =============================================================================

    # Debugging break point - inspect simulation objects here
    pass  # Set breakpoint here to verify  names and properties


    simulation_start_time = time.time()
    simulation_aborted = False
    # =============================================================================
    # SIMULATION EXECUTION LOOP
    # =============================================================================
    for current_step in range(N_SIM_STEPS):
        if simulation_aborted:
            break
        
        # Display current simulation time
        current_sim_time = Simulation.integrador.CurrentTime.GetValue(TIME_STEP_UNIT)
        print(f"Step {current_step + 1}/{N_SIM_STEPS}: "
            f"Simulation Time = {current_sim_time:.4f} {TIME_STEP_UNIT}")
        # -------------------------------------------------------------------------

        # MODIFICATION POINT - Add your custom changes here based on the current_step
        if current_step == 3: # Apply disturbances at specific step (e.g., change setpoint at step 3)
            continue

        # -------------------------------------------------------------------------
        # Advance simulation step
        try:
            Simulation.update(TIME_STEP_SIZE, TIME_STEP_UNIT)
        except Exception as e:
            print(f"Simulation error at step {current_step + 1}: {str(e)}")
            simulation_aborted = True
            traceback.print_exc()

    if not simulation_aborted:
        # Calculate and display performance metrics
        simulation_end_time = time.time()
        total_sim_time = simulation_end_time - simulation_start_time
        print(f"\nSimulation completed in {total_sim_time:.4f} seconds")

        quit_unisim = True # Quit UniSim if completed normally
    
    else:
        quit_unisim = False # Don't quit UniSim if aborted

    Simulation.finish(quit_unisim, SAVE_SIMULATION, EXPORT_CSV)
    pass



if __name__ == '__main__':
    main()



"""
    Main simulation control loop with modification guidelines and debugging tools.

    CONTROL MODIFICATION GUIDE:
    --------------------------
    1. STEP-BASED DISTURBANCES (Discrete changes at specific steps):
    if current_step == 3:  # After 3 time steps (0.099 minutes)
        Simulation.controllers['PIC-SC'].SP.SetValue(60, 'bar')  # Change setpoint
        Simulation.valves['LV-001'].ActuatorPosition.SetValue(100, '%')  # Open valve


    DEBUGGING UTILITIES:
    --------------------
    Set breakpoint below to inspect Operations:

    1. DISCOVER OPERATIONS:
    print("MaterialStreams:", Simulation.material_streams.names)
    print("Controllers:", Simulation.controllers.names)
    print("Valves:", Simulation.valves.names)

    2. INSPECT PROPERTIES:
    print(dir(Simulation.material_streams['Stream01']))  # All available methods
    print(dir

    3. ACCESS DATA:
    print("Stream values:", Simulation.material_streams.data['S-101'])
    print("Controller history:", Simulation.controllers.data['controller_name'])

    4. LIVE MONITORING :
    print("Temperature:", Simulation.material_streams['stream_name'].Temperature.GetValue('C'))
    print("PV:", Simulation.controllers['controller_name'].PV.GetValue(''))
    print("Valve Position:", Simulation.valves['valve_name'].ActuatorPosition.GetValue('%'))

    TROUBLESHOOTING:
    ----------------
    • Verify Operation names exist before access
    • .data contains pandas DataFrames with time-indexed simulation history
    • Check if Operation call is GetValue('unit or (leave it blank)') or GetValues('')  
    • Check units when setting/getting values use .GetValue('') if in doubt 
"""