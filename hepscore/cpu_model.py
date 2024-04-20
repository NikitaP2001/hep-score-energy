
class CpuModel:
    """
    A class representing intel CPU models with a dictionary for name mapping.
    """
    CPU_SANDYBRIDGE = 42
    CPU_SANDYBRIDGE_EP = 45
    CPU_IVYBRIDGE =	58
    CPU_IVYBRIDGE_EP = 62
    CPU_HASWELL = 60
    CPU_HASWELL_ULT = 69
    CPU_HASWELL_GT3E = 70
    CPU_HASWELL_EP = 63
    CPU_BROADWELL =	61
    CPU_BROADWELL_GT3E = 71
    CPU_BROADWELL_EP = 79
    CPU_BROADWELL_DE = 86
    CPU_SKYLAKE = 78
    CPU_SKYLAKE_HS = 94
    CPU_SKYLAKE_X =	85
    CPU_KNIGHTS_LANDING = 87
    CPU_KNIGHTS_MILL = 133
    CPU_KABYLAKE_MOBILE = 142
    CPU_KABYLAKE = 158
    CPU_ATOM_SILVERMONT = 55
    CPU_ATOM_AIRMONT = 76
    CPU_ATOM_MERRIFIELD = 74
    CPU_ATOM_MOOREFIELD = 90
    CPU_ATOM_GOLDMONT = 92
    CPU_ATOM_GEMINI_LAKE = 122
    CPU_ATOM_DENVERTON = 95

    CPU_MODELS = {
        42: "Sandybridge",
        45: "Sandybridge-EP",
        58: "Ivybridge",
        62: "Ivybridge-EP",
        60: "Haswell",
        69: "Haswell-ULT",
        70: "Haswell-GT3E",
        63: "Haswell-EP",
        61: "Broadwell",
        71: "Broadwell-GT3E",
        79: "Broadwell-EP",
        86: "Broadwell-DE",
        78: "Skylake",
        94: "Skylake-HS",
        85: "Skylake-X",
        87: "Knights Landing",
        133: "Knights Mill",
        142: "Kaby Lake Mobile",
        158: "Kaby Lake",
        55: "Atom Silvermont",
        76: "Atom Airmont",
        74: "Atom Merrifield",
        90: "Atom Moorefield",
        92: "Atom Goldmont",
        122: "Atom Gemini Lake",
        95: "Atom Denverton",
    }

    @staticmethod
    def get_model_name(model_number):
        return CpuModel.CPU_MODELS.get(model_number, None)