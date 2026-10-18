# Build manifest for the supplied CFS plugin after placeholder pruning.
Gem::Specification.new do |spec|
  spec.name = "openc3-cosmos-cfs"
  spec.version = ENV.fetch("VERSION")
  spec.summary = "OpenC3 CFS plugin for the SpaceCOP lab"
  spec.description = "Command, telemetry, and operator procedures for the pinned SpaceCOP CFS stack"
  spec.license = "MIT"
  spec.authors = ["Anonymous"]
  spec.email = ["name@domain.com"]
  spec.homepage = "https://github.com/OpenC3/cosmos"
  spec.platform = Gem::Platform::RUBY
  spec.required_ruby_version = ">= 3.0"

  spec.files = Dir.glob("{targets,lib,public,tools,microservices}/**/*") +
               %w[Rakefile README.md LICENSE.md plugin.txt]
end
