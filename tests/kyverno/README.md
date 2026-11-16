# Custom policy checks

Run `kyverno test tests/kyverno` with Kyverno CLI 1.20.0. These checks cover allowed and violating workloads, namespace exceptions, and the latest-tag escape label. The deployed policies remain Audit-only with background scans disabled. The CLI reports violations as failed evaluations; the test expectations verify those violations deliberately.

Pod policies explicitly match all seven controller kinds covered by the original
ClusterPolicy auto-generation, including legacy ReplicationController. The CEL
podSpec variable selects the appropriate Pod, controller or CronJob template.
Controller fixtures verify positive/negative image and resource checks plus
inherited namespace exceptions. An excluded result is not evidence of coverage:
non-exempt controller cases must have an evaluated validation result.
