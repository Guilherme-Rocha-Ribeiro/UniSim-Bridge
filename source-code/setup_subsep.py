# -*- coding: utf-8 -*-
"""
CONFIGURAÇÃO DO SETUP.PY - UNISIM CONNECTOR

Este arquivo configura quais operações serão monitoradas durante a simulação.
Todos os nomes devem corresponder exatamente aos nomes no arquivo .usc.

Use as funções de debugging para identificar os nomes disponíveis:
- get_material_streams()
- get_controllers() 
- get_valves()
- etc.
"""

# r"caminho/do/arquivo.usc -> Use copy as path from windows explorer and replace \ with /"
path_unisim = r"path/to/your/file.usc"

# Subflowsheets para monitorar (lista vazia se nenhum)
SUBFLOWSHEETS: list[str] = []

# Correntes materiais para monitorar
MATERIAL_STREAMS: list[str] = [
    'feed_sep', 'liq sep', 'gas_sep', '1', '3', '4', '5', '7', '18', '19', 
    '20', '21', '24', '17', 'S27', 'pump_1_out', '23', '25', 'pump_1_in',
    'pump_2_out', '23-2', '25-2', 'pump_2_in', '28', '8', '9', '10', '11', 
    '12', '13', '1st_heat_out', '15', '6', 'scrubber_in', '8-2', '9-2', 
    '10-2', '11-2', '12-2', '13-2', '2nd_heat_out', '15-2', '16-2', '30', 
    '32', '33', '34', 'prod well+', 'prod flow', 'poço de produção'
]

# Correntes materiais para monitorar fase específica
MATERIAL_STREAMS_PHASE: list[str] = ['pump_1_in', 'pump_2_out']

# Flashtanks para monitorar
FLASHTANKS: list[str] = ['V-100', 'V-101']

# Controladores para monitorar
CONTROLLERS: list[str] = ['LIC-100', 'LIC-101', 'LIC-102']

# Válvulas para monitorar
VALVES: list[str] = [
    'VLV-100', 'VLV-101', 'VLV-102', 'VLV-103', 'VLV-104', 'VLV-107', 
    'VLV-109', 'VLV-111', 'VLV-110', 'VLV-110-2', 'Valve_bypass_1', 
    'Valve_heat_1', 'VLV-106', 'Valve_bypass_2', 'Valve_heat_2', 
    'VLV-106-2', 'VLV-112', 'VLV-108'
]

# Trocadores de calor para monitorar
HEAT_EXCHANGERS: list[str] = ['E-100', 'E-100-2']

# Compressores para monitorar
COMPRESSORS: list[str] = ['pump_1', 'pump_2']

# Bombas para monitorar (lista vazia se nenhum)
PUMPS: list[str] = []

# Pipes names
PIPES: list[str] = []

# Aquecedores para monitorar
HEATERS: list[str] = []

# Resfriadores para monitorar
COOLERS: list[str] = []

# Planilhas para monitorar (dicionário vazio se nenhum)
SPREADSHEETS: dict[str, list[str]] = {}
