#!/usr/bin/env python3
from aws_cdk import App

from stark_infra.stark_stack import StarkInfraStack

app = App()
StarkInfraStack(app, "StarkbankChallengeStack")
app.synth()
