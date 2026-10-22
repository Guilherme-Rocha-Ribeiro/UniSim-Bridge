# Standard library
import os
import sys
import time
import traceback

# Setting path for local modules before importing them
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

# Local modules
from UnisimConnector import SimulationConnector
import setup_subsep


def main():
    # =========================================================================
    # SIMULATION CONFIG
    # =========================================================================
    OUTPUT_FOLDER = os.path.join(script_dir, 'output_folder')
    DB_NAME = os.path.join(script_dir, 'simulation.db')
    SIMULATION_TAG = 'test_run'

    # Simulation control flags
    CONTINUE_SIMULATION = False    # Resume from last saved state if True  
    SAVE_SIMULATION = False        # Save last simulation state to .usc when finished 
    SHOW_INTERFACE = True          # Display UniSim GUI during execution
    EXPORT_CSV = False             # Export the data to csv file

    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    print("Initializing Simulation Connector...")
    Simulation = SimulationConnector(
        setup_subsep.PATH_UNISIM, 
        OUTPUT_FOLDER, 
        SIMULATION_TAG, 
        DB_NAME, 
        CONTINUE_SIMULATION, 
        SHOW_INTERFACE
    )
        
    # Load variables from setup_subsep.py
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

    # =========================================================================
    # BUILD OBJECTS
    # =========================================================================
    print("Initializing build_objects()...")
    try:
        start = time.time()
        Simulation.build_objects(setup_subsep.SUBFLOWSHEETS)
        end = time.time()
        print(f"Build worked successfully in {(end - start):.6f} seconds")
    except Exception as e:
        print(f"Initialization failed: {str(e)}")
        traceback.print_exc()
        return  # Abort if initialization fails


if __name__ == '__main__':
    main()