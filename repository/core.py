from artiq.experiment import EnvExperiment
from artiq.language.core import rpc

class TestCore(EnvExperiment):
	def build(self):
		self.setattr_device("core")

	@rpc
	def run(self):
		print("BEC is ready, we will show it in December")