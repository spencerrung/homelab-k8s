# Custom policy checks

Run `kyverno test tests/kyverno` with Kyverno CLI 1.20.0. These checks cover allowed and violating workloads, namespace exceptions, and the latest-tag escape label. The deployed policies remain Audit-only with background scans disabled. The CLI reports violations as failed evaluations; the test expectations verify those violations deliberately.
