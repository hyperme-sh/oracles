"""v0 publishes no domain events.

Prefer silence on the bus. If a later slice publishes, use
``controlplane.events.v1`` only — never a per-product topic.
Payloads must never include prompt bodies, API keys, observed
upstream bytes, or other secrets. Do not write Gun.
"""
