from enum import Enum


# --- TEST LOCATIONS CONFIGURATION ---
class PresetLocation(str, Enum):
    # Highly populated (Major metropolitan areas)
    HIGH_DENSITY_PARIS = "High Density - Paris"
    HIGH_DENSITY_LYON = "High Density - Lyon"
    HIGH_DENSITY_MARSEILLE = "High Density - Marseille"

    # Moderately populated (Medium-sized cities)
    MEDIUM_DENSITY_TOURS = "Medium Density - Tours"
    MEDIUM_DENSITY_ANNECY = "Medium Density - Annecy"
    MEDIUM_DENSITY_LA_ROCHELLE = "Medium Density - La Rochelle"

    # Sparsely populated (Rural areas)
    LOW_DENSITY_MENDE = "Low Density - Mende (Lozère)"
    LOW_DENSITY_GUERET = "Low Density - Guéret (Creuse)"
    LOW_DENSITY_FLORAC = "Low Density - Florac (Cévennes)"


# Exact coordinate mapping (Latitude, Longitude)
PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING = {
    PresetLocation.HIGH_DENSITY_PARIS: (48.8566, 2.3522),
    PresetLocation.HIGH_DENSITY_LYON: (45.7640, 4.8357),
    PresetLocation.HIGH_DENSITY_MARSEILLE: (43.2965, 5.3698),
    PresetLocation.MEDIUM_DENSITY_TOURS: (47.3941, 0.6848),
    PresetLocation.MEDIUM_DENSITY_ANNECY: (45.8992, 6.1294),
    PresetLocation.MEDIUM_DENSITY_LA_ROCHELLE: (46.1603, -1.1511),
    PresetLocation.LOW_DENSITY_MENDE: (44.5176, 3.5000),
    PresetLocation.LOW_DENSITY_GUERET: (46.1667, 1.8667),
    PresetLocation.LOW_DENSITY_FLORAC: (44.3239, 3.5971),
}
