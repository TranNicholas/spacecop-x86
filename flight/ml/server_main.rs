//! Runtime-only entry point for the supplied SpaceCOP inference server.

use spacecop_ml::{BroadcastServer, INPUT_PORT, SPACECOP_ALERT_PORT};
use std::path::Path;

fn main() {
    let database = "instance/cmd_tlm.sqlite";
    let models = Path::new("scml_models");
    println!("Using database at: {database}");

    let server = BroadcastServer::new(database, models, INPUT_PORT, SPACECOP_ALERT_PORT)
        .unwrap_or_else(|error| {
            eprintln!("Failed to initialize server: {error}");
            std::process::exit(1);
        });
    server.start().expect("Failed to start server");
}
