"""Enable the supplied TO_LAB downlink to the COSMOS ground station."""

from openc3.script import cmd


destination = "cosmos"
cmd("TO_LAB", "TO_DEBUG_ENABLE_OUTPUT_CC", {"DEST_IP": destination})
print(f"TO_LAB downlink armed to {destination}")
