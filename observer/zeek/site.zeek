@load ./ccsds_analyzer.zeek
@load policy/tuning/json-logs.zeek
redef LogAscii::use_json = T;
redef LogAscii::json_timestamps = JSON::TS_ISO8601;
# Zeek 8 selects UDP content delivery through this option. The upstream
# analyzer's older orig/resp tables alone compile but produce no CCSDS logs.
redef udp_content_ports += { CCSDS::COMMAND_PORT, CCSDS::TELEMETRY_PORT };
