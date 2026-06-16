"""
session_analysis/report_generator.py — Session-level Go/No-Go report generation.

SessionReportGenerator aggregates per-sample ModelStack.predict() results into a
structured report dict and renders it as a human-readable 80-column terminal summary.
"""
import datetime
import textwrap
from collections import Counter
from typing import Any, Dict, List


class SessionReportGenerator:
    """Aggregate per-sample ML results into a structured session report.

    Usage::

        results = [ms.predict(sample) for sample in session_samples]
        report  = SessionReportGenerator().generate(results)
        print(SessionReportGenerator.to_text_summary(report))
    """

    def generate(self, session_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build a full session report from a list of predict() result dicts.

        Args:
            session_data: List of ModelStack.predict() output dicts, one per sample.
                Each dict has keys: steady_state, detection, isolation, decision,
                metadata.

        Returns:
            Structured report dict with keys:
            ``header``, ``session_summary``, ``leak_analysis``,
            ``recommendation``, ``data_summary``.
        """
        if not session_data:
            return self._empty_report()

        n = len(session_data)
        detections = [r["detection"] for r in session_data]
        decisions = [r["decision"] for r in session_data]
        isolations = [r.get("isolation", {}) for r in session_data]
        steady_states = [r["steady_state"] for r in session_data]

        leak_count = sum(1 for d in detections if d["is_leak"])
        leak_rate = leak_count / n

        z_cumulatives = [d["z_cumulative"] for d in detections]
        mean_z = sum(z_cumulatives) / n
        max_z = max(z_cumulatives)

        steady_count = sum(1 for s in steady_states if s["is_steady"])
        steady_rate = steady_count / n

        flag_counts = Counter(d["flag"] for d in decisions)
        fail_count = flag_counts.get("FAIL", 0)
        warning_count = flag_counts.get("WARNING", 0)

        go_nogo = self._determine_go_nogo(leak_rate, fail_count, n)

        zone_counter: Counter = Counter()
        zone_confidences: Dict[str, List[float]] = {}
        for iso in isolations:
            zone = iso.get("detected_zone")
            if zone:
                zone_counter[zone] += 1
                scores = iso.get("zone_scores", {})
                for z, score in scores.items():
                    zone_confidences.setdefault(z, []).append(score)

        top_zone = zone_counter.most_common(1)[0][0] if zone_counter else None
        zone_breakdown = {
            zone: {
                "count": cnt,
                "pct": round(cnt / n * 100, 1),
                "mean_confidence": round(
                    sum(zone_confidences.get(zone, [0])) /
                    max(len(zone_confidences.get(zone, [1])), 1),
                    4,
                ),
            }
            for zone, cnt in zone_counter.items()
        }

        severities = Counter(d.get("severity", "none") for d in decisions)
        action = self._pick_recommendation(go_nogo, top_zone, isolations, decisions)

        subsystem_means = {
            sub: round(sum(d["subsystem_z"][sub] for d in detections) / n, 4)
            for sub in ("boost", "dpf", "maf", "exhaust")
        }

        return {
            "header": {
                "report_timestamp": datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
                "sample_count": n,
                "go_nogo": go_nogo,
                "verdict_summary": self._verdict_line(go_nogo, leak_count, n),
            },
            "session_summary": {
                "leak_count": leak_count,
                "leak_rate_pct": round(leak_rate * 100, 2),
                "mean_z_cumulative": round(mean_z, 4),
                "max_z_cumulative": round(max_z, 4),
                "steady_rate_pct": round(steady_rate * 100, 2),
                "flag_counts": dict(flag_counts),
                "fail_count": fail_count,
                "warning_count": warning_count,
                "severity_counts": dict(severities),
            },
            "leak_analysis": {
                "top_zone": top_zone,
                "zone_breakdown": zone_breakdown,
                "samples_with_zone": sum(zone_counter.values()),
                "subsystem_z_means": subsystem_means,
                "mean_svm_z": round(sum(d["svm_z"] for d in detections) / n, 4),
                "mean_mahal_z": round(sum(d["mahal_z"] for d in detections) / n, 4),
            },
            "recommendation": {
                "action": action,
                "escalate_immediately": any(
                    d.get("escalate_immediately") for d in decisions
                ),
                "top_zone_label": self._zone_label(top_zone),
            },
            "data_summary": {
                "z_cumulative_min": round(min(z_cumulatives), 4),
                "z_cumulative_p50": round(sorted(z_cumulatives)[n // 2], 4),
                "z_cumulative_p95": round(
                    sorted(z_cumulatives)[int(n * 0.95)], 4
                ),
                "z_cumulative_max": round(max_z, 4),
            },
        }

    @staticmethod
    def to_text_summary(report: Dict[str, Any]) -> str:
        """Render a report dict as an 80-column terminal summary.

        Args:
            report: Dict from SessionReportGenerator.generate().

        Returns:
            Formatted multi-line string with box-drawing borders.
        """
        # Total box width = 80.
        # CW = content width (text area inside ║ margins).
        # BW = border width (number of ═/─ chars between corner chars).
        # Relationship: 1 + 1 + CW + 1 + 1 = 80  →  CW = 76.
        #               1 + BW + 1 = 80            →  BW = 78.
        CW, BW = 76, 78

        def line(text: str = "") -> str:
            return f"║ {text[:CW]:<{CW}} ║"

        def wrapped_lines(text: str) -> list:
            return [line(ln) for ln in textwrap.wrap(text, width=CW)] or [line("")]

        def divider() -> str:
            return f"╟{'─' * BW}╢"

        hdr = report.get("header", {})
        summ = report.get("session_summary", {})
        leak = report.get("leak_analysis", {})
        rec = report.get("recommendation", {})
        data = report.get("data_summary", {})

        go_nogo = hdr.get("go_nogo", "UNKNOWN")
        verdict = hdr.get("verdict_summary", "")
        ts = hdr.get("report_timestamp", "")[:19].replace("T", " ")

        lines = [
            f"╔{'═' * BW}╗",
            line("DIESEL ENGINE LEAK DETECTION — SESSION REPORT"),
            line(f"Generated: {ts}   Samples: {hdr.get('sample_count', '?')}"),
            f"╠{'═' * BW}╣",
            *wrapped_lines(f"VERDICT: {go_nogo}   —   {verdict}"),
            f"╠{'═' * BW}╣",
            line("SESSION SUMMARY"),
            divider(),
            line(
                f"Leak rate:   {summ.get('leak_rate_pct', 0):>6.1f}%"
                f"   ({summ.get('leak_count', 0)} / {hdr.get('sample_count', '?')} samples)"
            ),
            line(
                f"Steady rate: {summ.get('steady_rate_pct', 0):>6.1f}%"
                f"   FAIL windows: {summ.get('fail_count', 0)}"
                f"   WARNING: {summ.get('warning_count', 0)}"
            ),
            line(
                f"z_cumulative  mean: {summ.get('mean_z_cumulative', 0):>7.3f}"
                f"   max: {summ.get('max_z_cumulative', 0):>7.3f}"
            ),
            f"╠{'═' * BW}╣",
            line("LEAK ANALYSIS"),
            divider(),
        ]

        top_zone = leak.get("top_zone")
        zone_bd = leak.get("zone_breakdown", {})
        if top_zone and zone_bd:
            lines.append(line(f"Dominant zone: {top_zone}   ({rec.get('top_zone_label', '')})"))
            for zone, stats in sorted(zone_bd.items()):
                bar_len = int(stats["pct"] / 2)
                bar = "█" * bar_len
                lines.append(
                    line(
                        f"  {zone:<8}  {stats['pct']:>5.1f}%  {bar}"
                    )
                )
        else:
            lines.append(line("  No zone isolations recorded — all samples normal."))

        sz = leak.get("subsystem_z_means", {})
        lines += [
            divider(),
            line(
                f"Subsystem z-bar  boost:{sz.get('boost', 0):>6.3f}"
                f"  dpf:{sz.get('dpf', 0):>6.3f}"
                f"  maf:{sz.get('maf', 0):>6.3f}"
                f"  exhaust:{sz.get('exhaust', 0):>6.3f}"
            ),
            line(
                f"                 svm_z:{leak.get('mean_svm_z', 0):>6.3f}"
                f"  mahal_z:{leak.get('mean_mahal_z', 0):>8.3f}"
            ),
            f"╠{'═' * BW}╣",
            line("RECOMMENDATION"),
            divider(),
        ]

        action_text = rec.get("action", "No action required.")
        for wrap_line in textwrap.wrap(action_text, width=CW):
            lines.append(line(wrap_line))

        if rec.get("escalate_immediately"):
            lines.append(line("ESCALATE IMMEDIATELY — stop test, notify supervisor."))

        lines += [
            f"╠{'═' * BW}╣",
            line("DATA PERCENTILES   (z_cumulative)"),
            divider(),
            line(
                f"  p50: {data.get('z_cumulative_p50', 0):>7.3f}"
                f"   p95: {data.get('z_cumulative_p95', 0):>7.3f}"
                f"   max: {data.get('z_cumulative_max', 0):>7.3f}"
            ),
            f"╚{'═' * BW}╝",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_go_nogo(
        leak_rate: float,
        fail_count: int,
        n: int,
    ) -> str:
        if leak_rate >= 0.20 or fail_count >= max(n * 0.10, 3):
            return "NO-GO"
        if leak_rate >= 0.05 or fail_count >= 1:
            return "CAUTION"
        return "GO"

    @staticmethod
    def _verdict_line(go_nogo: str, leak_count: int, n: int) -> str:
        if go_nogo == "NO-GO":
            return f"Leak confirmed in {leak_count}/{n} samples. Do not release engine."
        if go_nogo == "CAUTION":
            return f"Marginal anomalies in {leak_count}/{n} samples. Re-run test."
        return f"No significant anomalies detected across {n} samples."

    @staticmethod
    def _zone_label(zone: str | None) -> str:
        labels = {
            "zone_1": "Pre-compressor intake",
            "zone_2": "Charge-air system",
            "zone_3": "Exhaust path",
            "zone_4": "Test-cell ducting",
            "multiple": "Multiple zones",
            "unknown": "Zone unclear",
        }
        return labels.get(zone or "unknown", "Zone unclear")

    @staticmethod
    def _pick_recommendation(
        go_nogo: str,
        top_zone: str | None,
        isolations: List[Dict],
        decisions: List[Dict],
    ) -> str:
        if go_nogo == "GO":
            return (
                "Session passed. Engine is operating within healthy parameters. "
                "Proceed with standard test cell sign-off procedure."
            )

        zone_actions = {
            "zone_1": (
                "Inspect pre-compressor intake hose and air filter housing. "
                "Check MAF sensor connections. Perform smoke test at inlet."
            ),
            "zone_2": (
                "Inspect charge-air circuit from compressor outlet to intake manifold. "
                "Check CAC end-tank seals, intercooler hoses, and boost clamps."
            ),
            "zone_3": (
                "Check aftertreatment inlet connection for soot trails indicating a hot-side "
                "exhaust leak. Inspect manifold-to-head gaskets and turbo outlet pipe."
            ),
            "zone_4": (
                "Check test cell ducting connections and measurement tap seals. "
                "Verify cell-to-engine interface flanges are properly sealed."
            ),
            "multiple": (
                "Multiple zones suspect. Perform systematic pressure-decay test. "
                "Begin with Zone 2 (charge-air) — most common failure location."
            ),
        }
        default = (
            "Leak detected but zone unclear. Perform visual inspection of all "
            "circuit interfaces. Consult steady-state test data records."
        )

        if go_nogo == "CAUTION":
            return (
                f"Marginal anomalies detected. "
                + zone_actions.get(top_zone or "unknown", default)
            )
        return zone_actions.get(top_zone or "unknown", default)

    @staticmethod
    def _empty_report() -> Dict[str, Any]:
        ts = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        return {
            "header": {
                "report_timestamp": ts,
                "sample_count": 0,
                "go_nogo": "GO",
                "verdict_summary": "No samples provided.",
            },
            "session_summary": {
                "leak_count": 0, "leak_rate_pct": 0.0,
                "mean_z_cumulative": 0.0, "max_z_cumulative": 0.0,
                "steady_rate_pct": 0.0, "flag_counts": {},
                "fail_count": 0, "warning_count": 0, "severity_counts": {},
            },
            "leak_analysis": {
                "top_zone": None, "zone_breakdown": {},
                "samples_with_zone": 0,
                "subsystem_z_means": {"boost": 0.0, "dpf": 0.0, "maf": 0.0, "exhaust": 0.0},
                "mean_svm_z": 0.0, "mean_mahal_z": 0.0,
            },
            "recommendation": {
                "action": "No samples provided — nothing to analyse.",
                "escalate_immediately": False,
                "top_zone_label": "Zone unclear",
            },
            "data_summary": {
                "z_cumulative_min": 0.0, "z_cumulative_p50": 0.0,
                "z_cumulative_p95": 0.0, "z_cumulative_max": 0.0,
            },
        }
