import os, sys, traceback
from UnisimConnector import SimulationConnector
import setup_subsep

def main():
    here = os.path.dirname(os.path.abspath(__file__)) # Get the directory of the current script
    sim = SimulationConnector(setup_subsep.path_unisim, os.path.join(here, 'out', ''),
                              'run01', os.path.join(here, 'run.db'),
                              continue_simulation=False, case_visible=True)
    sim.easy_setup(
        pumps=setup_subsep.PUMPS, valves=setup_subsep.VALVES, flashtanks=setup_subsep.FLASHTANKS, compressors=setup_subsep.COMPRESSORS,
        controllers=setup_subsep.CONTROLLERS, heat_exchangers=setup_subsep.HEAT_EXCHANGERS,
        material_streams=setup_subsep.MATERIAL_STREAMS, material_streams_phase=setup_subsep.MATERIAL_STREAMS_PHASE,
        heaters=setup_subsep.HEATERS, coolers=setup_subsep.COOLERS, pipes=setup_subsep.PIPES, spreadsheets=setup_subsep.SPREADSHEETS,
    )
    sim.build_objects(setup_subsep.SUBFLOWSHEETS)

    aborted = False
    for step in range(100):
        try:
            sim.update(0.033, 'minutes')
        except Exception:
            traceback.print_exc()
            aborted = True
            break

    sim.finish(quit_unisim=not aborted, save_simulation=False, export_csv=True)

    pass # add a debug break point here 
if __name__ == '__main__':
    main()