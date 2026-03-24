plywatch documentation
======================

Plywatch is an ephemeral Celery monitor with an embedded web UI. It is designed
to be easy to run, easy to inspect, and operationally lightweight.

Security note: Plywatch is intended for internal/trusted environments. Deploy it
behind an authenticated TLS-terminating proxy; do not expose it directly to the
public internet.

The docs here are intentionally short:

- what Plywatch is for
- how to run it
- how to configure it
- where Celery and loom-kernel documentation live for deeper details

.. toctree::
   :maxdepth: 2
   :caption: Guides

   README
   guides/quickstart
   guides/configuration
   guides/architecture
   observed/celery_observed_events
   observed/celery_worker_observed_events
