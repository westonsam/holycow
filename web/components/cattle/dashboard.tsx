"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  LayoutDashboard,
  Map,
  Table2,
  Plane,
  Settings,
  Search,
  ChevronRight,
  ChevronDown,
  ArrowUpRight,
  Plus,
  Download,
  RefreshCw,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCheck,
  CircleHelp,
  Radio,
  Clock3,
  MapPin,
  X,
  Loader2,
  SlidersHorizontal,
  CalendarDays,
  Bell,
  RotateCcw,
  ShieldCheck,
  Eye,
  Activity,
  Star,
} from "lucide-react";
import type {
  Animal,
  Assessment,
  Flight,
  Overview,
  ReviewReceipt,
  Section,
} from "@/lib/cattle/contracts";
import { monitoringApi } from "@/lib/cattle/client";
import { CowMark } from "./icons";
import { Dialog } from "./dialog";
import { PastureMap } from "./pasture-map";
import { assessmentLabels, Dot, StatusBadge, time } from "./status";
import { Spotlight } from "./spotlight";

const STORAGE = "holycow.workspace.v1";
type Modal =
  | "about"
  | "settings"
  | "profile"
  | "search"
  | "add-animal"
  | "plan-flight"
  | "ranch"
  | null;
interface Preferences {
  boundaries: boolean;
  staleMinutes: number;
}
interface LocalState {
  favoriteIds: string[];
  reviews: ReviewReceipt[];
  animals: Animal[];
  flights: Flight[];
  preferences: Preferences;
}
const emptyLocal: LocalState = {
  favoriteIds: ["cow-718", "cow-904", "cow-652"],
  reviews: [],
  animals: [],
  flights: [],
  preferences: { boundaries: true, staleMinutes: 60 },
};
const sections: { id: Section; label: string; icon: typeof Map }[] = [
  { id: "overview", label: "Herd overview", icon: LayoutDashboard },
  { id: "map", label: "Pasture map", icon: Map },
  { id: "cattle", label: "Cattle register", icon: Table2 },
  { id: "spotlight", label: "Spotlight", icon: Star },
  { id: "flights", label: "Flight log", icon: Plane },
];

export default function Dashboard() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [section, setSection] = useState<Section>("overview");
  const [local, setLocal] = useState<LocalState>(emptyLocal);
  const [ready, setReady] = useState(false);
  const [modal, setModal] = useState<Modal>(null);
  const [selectedAnimal, setSelectedAnimal] = useState<string | null>(null);
  const [selectedFlight, setSelectedFlight] = useState<Flight | null>(null);
  const [herdFilter, setHerdFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sortAsc, setSortAsc] = useState(true);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [showAllAlerts, setShowAllAlerts] = useState(false);
  const [toast, setToast] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewError, setReviewError] = useState("");
  const [busy, setBusy] = useState(false);
  const [detailTab, setDetailTab] = useState<"summary" | "history">("summary");
  const [formError, setFormError] = useState("");
  const [tag, setTag] = useState("");
  const [newHerd, setNewHerd] = useState("herd-1");
  const [flightName, setFlightName] = useState("");

  const notify = useCallback((message: string) => setToast(message), []);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await monitoringApi.overview());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load observations.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE) || "null");
      if (
        stored &&
        Array.isArray(stored.reviews) &&
        Array.isArray(stored.animals) &&
        Array.isArray(stored.flights)
      ) {
        setLocal({
          ...emptyLocal,
          ...stored,
          favoriteIds: Array.isArray(stored.favoriteIds)
            ? stored.favoriteIds.filter((id: unknown) => typeof id === "string")
            : emptyLocal.favoriteIds,
          preferences: { ...emptyLocal.preferences, ...stored.preferences },
        });
      }
    } catch {
      /* Invalid or disabled local storage leaves the clean demo usable. */
    }
    setReady(true);
  }, []);
  useEffect(() => {
    if (ready) {
      try {
        localStorage.setItem(STORAGE, JSON.stringify(local));
      } catch {
        /* Session remains functional without persistence. */
      }
    }
  }, [local, ready]);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  useEffect(() => {
    setPage(1);
    setSelectedRows([]);
  }, [query, herdFilter, statusFilter]);
  useEffect(() => {
    const shortcut = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        !(e.target as HTMLElement).closest("input,textarea,select")
      ) {
        e.preventDefault();
        setSearch("");
        setModal("search");
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  const closeModal = useCallback(() => {
    setModal(null);
    setFormError("");
  }, []);
  const closeAnimal = useCallback(() => {
    if (!busy) setSelectedAnimal(null);
  }, [busy]);
  const closeFlight = useCallback(() => setSelectedFlight(null), []);
  const animals = useMemo(
    () => [...(data?.animals ?? []), ...local.animals],
    [data, local.animals],
  );
  const alerts = useMemo(
    () =>
      (data?.alerts ?? []).map((alert) => {
        const changes = local.reviews.filter((r) => r.alertId === alert.id);
        const latest = changes[changes.length - 1];
        return latest
          ? { ...alert, lifecycle: latest.lifecycle, revision: latest.revision }
          : alert;
      }),
    [data, local.reviews],
  );
  const flights = [...local.flights, ...(data?.flights ?? [])];
  const activeAlerts = alerts.filter((a) =>
    ["open", "acknowledged"].includes(a.lifecycle),
  );
  const animal = animals.find((a) => a.id === selectedAnimal);
  const animalAlert = alerts.find((a) => a.animalId === selectedAnimal);
  const detailHistory = local.reviews.filter(
    (r) => r.alertId === animalAlert?.id,
  );
  const filteredAnimals = useMemo(
    () =>
      animals
        .filter(
          (a) =>
            (herdFilter === "all" || a.herdId === herdFilter) &&
            (statusFilter === "all" ||
              (statusFilter === "attention"
                ? ["priority", "review", "unable"].includes(a.assessment)
                : a.assessment === statusFilter)) &&
            (!query ||
              `cow ${a.tag} ${a.id}`
                .toLowerCase()
                .includes(query.toLowerCase().trim())),
        )
        .sort(
          (a, b) =>
            a.tag.localeCompare(b.tag, undefined, { numeric: true }) *
            (sortAsc ? 1 : -1),
        ),
    [animals, herdFilter, statusFilter, query, sortAsc],
  );
  const totalPages = Math.max(1, Math.ceil(filteredAnimals.length / 12));
  const pageAnimals = filteredAnimals.slice((page - 1) * 12, page * 12);
  const openAnimal = (a: Animal) => {
    setSelectedAnimal(a.id);
    setReviewNote("");
    setReviewError("");
    setDetailTab("summary");
  };
  const toggleFavorite = (id: string) => {
    setLocal((current) => ({
      ...current,
      favoriteIds: current.favoriteIds.includes(id)
        ? current.favoriteIds.filter((value) => value !== id)
        : [...current.favoriteIds, id],
    }));
  };
  const navigate = (target: Section) => {
    setSection(target);
    setSelectedRows([]);
  };
  const changeSection = (target: Section) => {
    navigate(target);
    setHerdFilter("all");
    setStatusFilter("all");
    setQuery("");
  };

  async function review(action: "acknowledge" | "accept" | "reject") {
    if (!animalAlert || busy) return;
    const reason =
      reviewNote.trim() ||
      (action === "acknowledge"
        ? "Acknowledged for follow-up in the demo workspace."
        : "");
    if (!reason) {
      setReviewError("Add a note explaining your review decision.");
      return;
    }
    setBusy(true);
    setReviewError("");
    try {
      const receipt = await monitoringApi.review(animalAlert.id, {
        action,
        reason,
        expectedRevision: animalAlert.revision,
        requestId: crypto.randomUUID(),
      });
      setLocal((s) => ({ ...s, reviews: [...s.reviews, receipt] }));
      setReviewNote("");
      notify(
        `Finding ${receipt.lifecycle === "invalidated" ? "rejected" : receipt.lifecycle}. Saved in this browser’s demo workspace.`,
      );
    } catch (e) {
      setReviewError(
        e instanceof Error ? e.message : "Could not save the review.",
      );
    } finally {
      setBusy(false);
    }
  }

  function exportCattle() {
    const rows = selectedRows.length
      ? filteredAnimals.filter((a) => selectedRows.includes(a.id))
      : filteredAnimals;
    const quote = (value: unknown) =>
      `"${String(value ?? "").replace(/"/g, '""')}"`;
    const csv = [
      ["Cow tag", "Herd", "Assessment", "Last observed (UTC)", "Data source"],
      ...rows.map((a) => [
        a.tag,
        data?.herds.find((h) => h.id === a.herdId)?.name,
        assessmentLabels[a.assessment],
        a.observedAt,
        "Demo data",
      ]),
    ]
      .map((row) => row.map(quote).join(","))
      .join("\r\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8;" }),
    );
    link.download = "holycow-demo-cattle.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    notify(`Exported ${rows.length} demo cattle records.`);
  }

  function addAnimal(e: React.FormEvent) {
    e.preventDefault();
    const value = tag.trim();
    if (!/^\d{1,12}$/.test(value)) {
      setFormError("Enter a numeric cow tag, up to 12 digits.");
      return;
    }
    if (animals.some((a) => a.tag === value)) {
      setFormError("That cow tag already exists in this demo workspace.");
      return;
    }
    const item: Animal = {
      id: `local-${crypto.randomUUID()}`,
      tag: value,
      herdId: newHerd,
      assessment: "unobserved",
      observedAt: null,
      mapPosition: null,
      metric: "Gait / locomotion",
      metricValue: "Not assessed",
      modelVersion: "No observations",
    };
    setLocal((s) => ({ ...s, animals: [...s.animals, item] }));
    setTag("");
    closeModal();
    setSection("cattle");
    setHerdFilter("all");
    setStatusFilter("all");
    setQuery(value);
    notify(`Cow ${value} added locally. Awaiting its first observation.`);
  }

  const map = data && (
    <PastureMap
      key={`map-${local.preferences.boundaries}`}
      animals={animals}
      nonCowDetections={data.nonCowDetections ?? []}
      herds={data.herds}
      herdFilter={herdFilter}
      setHerdFilter={setHerdFilter}
      openAnimal={openAnimal}
      expanded={section === "map"}
      onExpand={() => setSection(section === "map" ? "overview" : "map")}
      initialBoundaries={local.preferences.boundaries}
    />
  );
  const demoButton = (
    <button className="demo-badge" onClick={() => setModal("about")}>
      <span />
      Demo data
    </button>
  );
  const searchButton = (
    <button
      className="icon-button search-trigger"
      aria-label="Search cattle and herds"
      title="Search (/)"
      onClick={() => {
        setSearch("");
        setModal("search");
      }}
    >
      <Search size={19} />
    </button>
  );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="sidebar" aria-label="Primary navigation">
        <button
          className="brand-mark"
          onClick={() => changeSection("overview")}
          aria-label="HolyCow home"
          title="HolyCow"
        >
          <CowMark />
        </button>
        <nav>
          {sections.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-button ${section === item.id ? "nav-active" : ""}`}
                onClick={() => changeSection(item.id)}
                disabled={!data}
                aria-label={item.label}
                aria-current={section === item.id ? "page" : undefined}
                title={item.label}
              >
                <Icon size={23} strokeWidth={1.55} />
                <span className="nav-tooltip">{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <button
            className="nav-button"
            onClick={() => setModal("settings")}
            aria-label="Workspace settings"
            title="Settings"
          >
            <Settings size={21} strokeWidth={1.5} />
            <span className="nav-tooltip">Settings</span>
          </button>
          <button
            className="profile-button"
            onClick={() => setModal("profile")}
            aria-label="Demo operator profile"
            title="Demo operator"
          >
            <span>JD</span>
            <i />
          </button>
        </div>
      </aside>

      <main id="main-content" className={`workspace workspace-${section}`}>
        {!data ? (
          <div className="loading-state">
            <CowMark size={48} />
            {loading ? (
              <>
                <Loader2 className="spin" size={23} />
                <h1>Gathering the herd…</h1>
                <p>Loading the demo observation snapshot.</p>
              </>
            ) : (
              <>
                <h1>We couldn’t load the herd</h1>
                <p>{error}</p>
                <button className="primary-button" onClick={() => void load()}>
                  Try again
                </button>
              </>
            )}
          </div>
        ) : (
          <>
            {section === "overview" ? (
              <div className="overview-grid">
                <div className="overview-column">
                  <header className="overview-header">
                    <button
                      className="ranch-switch"
                      onClick={() => setModal("ranch")}
                    >
                      {data.ranch}
                      <ChevronDown size={12} />
                    </button>
                    <div className="title-row">
                      <h1>Herd overview</h1>
                      <div className="header-actions">
                        {searchButton}
                        {demoButton}
                      </div>
                    </div>
                    <div className="observation-subtitle">
                      Latest observations <span>•</span> Today,{" "}
                      {time(data.snapshotAt)}
                      <button
                        className={`refresh-button ${loading ? "is-refreshing" : ""}`}
                        onClick={() => {
                          void load();
                          notify("Refreshing the demo observation snapshot.");
                        }}
                        disabled={loading}
                        aria-label="Refresh observations"
                      >
                        <RefreshCw size={13} />
                      </button>
                    </div>
                  </header>

                  <section className="card alerts-card">
                    <div className="card-title">
                      <h2>
                        Alerts{" "}
                        <span className="count-pill">
                          {activeAlerts.length}
                        </span>
                      </h2>
                      <button
                        className={`icon-button small ${showAllAlerts ? "subtle-active" : ""}`}
                        aria-label={
                          showAllAlerts
                            ? "Show open alerts"
                            : "Include reviewed alerts"
                        }
                        title={
                          showAllAlerts
                            ? "Show open alerts"
                            : "Include reviewed alerts"
                        }
                        onClick={() => setShowAllAlerts(!showAllAlerts)}
                      >
                        <SlidersHorizontal size={16} />
                      </button>
                    </div>
                    {(showAllAlerts ? alerts : activeAlerts).map((alert) => {
                      const a = animals.find((a) => a.id === alert.animalId)!;
                      return (
                        <button
                          className="alert-row"
                          key={alert.id}
                          onClick={() => openAnimal(a)}
                        >
                          <span className="alert-animal">
                            <Dot status={alert.severity} />
                            <strong>Cow {a.tag}</strong>
                          </span>
                          <StatusBadge status={alert.severity} />
                          <span className="alert-time">
                            {["resolved", "invalidated"].includes(
                              alert.lifecycle,
                            )
                              ? alert.lifecycle === "resolved"
                                ? "Reviewed"
                                : "Rejected"
                              : `Today, ${time(alert.observedAt)}`}
                          </span>
                          <ChevronRight size={17} />
                        </button>
                      );
                    })}
                    {!activeAlerts.length && !showAllAlerts && (
                      <div className="empty-alerts">
                        <CheckCheck size={25} />
                        <strong>All findings reviewed</strong>
                        <button
                          className="text-button"
                          onClick={() => setShowAllAlerts(true)}
                        >
                          View review history
                        </button>
                      </div>
                    )}
                    {showAllAlerts && (
                      <p className="card-footnote">
                        Includes reviewed and rejected demo findings.
                      </p>
                    )}
                  </section>

                  <div className="herd-cards">
                    {data.herds.map((herd) => {
                      const members = animals.filter(
                        (a) => a.herdId === herd.id,
                      );
                      const counts = (status: Assessment) =>
                        members.filter((a) => a.assessment === status).length;
                      return (
                        <button
                          key={herd.id}
                          className="card herd-card"
                          onClick={() => {
                            setHerdFilter(herd.id);
                            setStatusFilter("all");
                            setQuery("");
                            navigate("cattle");
                          }}
                          aria-label={`Open ${herd.name}, ${members.length} cows`}
                        >
                          <div className="herd-card-title">
                            <h2>
                              <span className="healthy-dot" />
                              {herd.name}
                            </h2>
                            <span className="cow-count">
                              {members.length} cows
                            </span>
                          </div>
                          <div
                            className="herd-chart"
                            aria-label={`${counts("priority")} priority, ${counts("review")} review, ${counts("clear")} no clear deviation`}
                          >
                            {(
                              ["priority", "review", "clear"] as Assessment[]
                            ).map((status) => (
                              <div
                                className={`chart-column chart-${status}`}
                                key={status}
                              >
                                <strong>{counts(status)}</strong>
                                <span
                                  className="chart-bar"
                                  style={{
                                    height: `${Math.max(5, (counts(status) / 45) * 92)}px`,
                                  }}
                                />
                                <span className="chart-label">
                                  {status === "priority"
                                    ? "Priority"
                                    : status === "review"
                                      ? "Review"
                                      : "No deviation"}
                                </span>
                              </div>
                            ))}
                          </div>
                          <div className="herd-card-footer">
                            <span>
                              {counts("unable")
                                ? `${counts("unable")} unable to assess · `
                                : ""}
                              {counts("unobserved")} unobserved
                            </span>
                            <ArrowUpRight size={13} />
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <section className="card drone-card">
                    <div className="card-title">
                      <h2>Drone status</h2>
                      <span className="landed-label">
                        <span />
                        Landed
                      </span>
                    </div>
                    <div className="drone-metrics">
                      <button
                        onClick={() => setSelectedFlight(data.flights[0])}
                      >
                        <span className="metric-label">Battery</span>
                        <strong className="battery-reading">
                          <span className="battery-meter">
                            <i style={{ width: "78%" }} />
                          </span>
                          78<span className="metric-unit">%</span>
                        </strong>
                      </button>
                      <button
                        onClick={() => setSelectedFlight(data.flights[0])}
                      >
                        <span className="metric-label">Last full sweep</span>
                        <strong>{time(data.snapshotAt)}</strong>
                      </button>
                      <button
                        onClick={() => {
                          navigate("cattle");
                          setStatusFilter("all");
                          setHerdFilter("all");
                        }}
                      >
                        <span className="metric-label">Cows observed</span>
                        <strong>
                          {animals.filter((a) => a.observedAt).length}
                          <span className="metric-denominator">
                            {" "}
                            / {animals.length}
                          </span>
                        </strong>
                      </button>
                      <button
                        onClick={() => setSelectedFlight(data.flights[0])}
                      >
                        <span className="metric-label">Coverage</span>
                        <strong>
                          91<span className="metric-unit">%</span>
                        </strong>
                      </button>
                    </div>
                    <div className="drone-footer">
                      <span>
                        <Radio size={12} />
                        Drone 01 · at last sweep
                      </span>
                      <button
                        className="text-button"
                        onClick={() => navigate("flights")}
                      >
                        Flight log
                        <ArrowUpRight size={13} />
                      </button>
                    </div>
                  </section>
                  <footer className="workspace-footer">
                    <span className="tiny-check">
                      <ShieldCheck size={13} /> Observations require human
                      review
                    </span>
                    <button
                      onClick={() => setModal("about")}
                      aria-label="About these observations"
                    >
                      <CircleHelp size={15} />
                    </button>
                  </footer>
                </div>
                {map}
              </div>
            ) : (
              <>
                <header className="page-header">
                  <div>
                    <button
                      className="ranch-switch"
                      onClick={() => setModal("ranch")}
                    >
                      {data.ranch}
                      <ChevronDown size={12} />
                    </button>
                    <h1>{sections.find((s) => s.id === section)?.label}</h1>
                    <p>
                      {section === "map"
                        ? "Last-known observations across your pastures."
                        : section === "cattle"
                          ? "Your herd, one animal at a time."
                          : section === "spotlight"
                            ? "Important cows. Their latest recorded moments."
                            : "Capture history and upcoming pasture checks."}
                    </p>
                  </div>
                  <div className="header-actions">
                    {searchButton}
                    {demoButton}
                  </div>
                </header>
                {section === "spotlight" && (
                  <Spotlight
                    animals={animals}
                    herds={data.herds}
                    alerts={alerts}
                    favoriteIds={local.favoriteIds}
                    toggleFavorite={toggleFavorite}
                    openAnimal={openAnimal}
                  />
                )}
                {section === "map" && (
                  <div className="map-page-layout">
                    <aside className="map-context card">
                      <div className="eyebrow">PASTURE OVERVIEW</div>
                      <h2>Know where to look.</h2>
                      <p>
                        Choose a herd to focus the map, or select an observation
                        for a closer look.
                      </p>
                      {data.herds.map((h) => (
                        <button
                          className={`pasture-list-item ${herdFilter === h.id ? "pasture-selected" : ""}`}
                          key={h.id}
                          onClick={() =>
                            setHerdFilter(herdFilter === h.id ? "all" : h.id)
                          }
                        >
                          <div>
                            <strong>
                              <span className="healthy-dot" />
                              {h.name}
                            </strong>
                            <span>{h.pasture}</span>
                          </div>
                          <span>
                            {animals.filter((a) => a.herdId === h.id).length}
                            <ChevronRight size={15} />
                          </span>
                        </button>
                      ))}
                      <div className="map-context-note">
                        <Clock3 size={17} />
                        <p>
                          These are intermittent observations, not live
                          positions. The background is illustrative.
                        </p>
                      </div>
                      <button
                        className="secondary-button"
                        onClick={() => {
                          setSection("overview");
                          setHerdFilter("all");
                        }}
                      >
                        <ArrowLeft size={15} />
                        Back to overview
                      </button>
                    </aside>
                    {map}
                  </div>
                )}
                {section === "cattle" && (
                  <section className="card register-card">
                    <div className="register-toolbar">
                      <div className="input-with-icon">
                        <Search size={17} />
                        <input
                          placeholder="Search cow tag…"
                          aria-label="Search cow tag"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                        {query && (
                          <button
                            className="input-clear"
                            onClick={() => setQuery("")}
                            aria-label="Clear search"
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                      <select
                        className="field-select"
                        aria-label="Filter cattle by herd"
                        value={herdFilter}
                        onChange={(e) => setHerdFilter(e.target.value)}
                      >
                        <option value="all">All herds</option>
                        {data.herds.map((h) => (
                          <option key={h.id} value={h.id}>
                            {h.name}
                          </option>
                        ))}
                      </select>
                      <select
                        className="field-select"
                        aria-label="Filter cattle by assessment"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                      >
                        <option value="all">All assessments</option>
                        <option value="attention">Needs attention</option>
                        {Object.entries(assessmentLabels).map(
                          ([key, label]) => (
                            <option key={key} value={key}>
                              {label}
                            </option>
                          ),
                        )}
                      </select>
                      <div className="toolbar-spacer" />
                      <button
                        className="secondary-button"
                        onClick={exportCattle}
                        disabled={!filteredAnimals.length}
                      >
                        <Download size={15} />
                        {selectedRows.length
                          ? `Export ${selectedRows.length}`
                          : "Export"}
                      </button>
                      <button
                        className="primary-button"
                        onClick={() => {
                          setFormError("");
                          setTag("");
                          setModal("add-animal");
                        }}
                      >
                        <Plus size={16} />
                        Add cow
                      </button>
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th className="checkbox-cell">
                              <input
                                type="checkbox"
                                aria-label="Select cattle on this page"
                                checked={
                                  !!pageAnimals.length &&
                                  pageAnimals.every((a) =>
                                    selectedRows.includes(a.id),
                                  )
                                }
                                onChange={(e) =>
                                  setSelectedRows(
                                    e.target.checked
                                      ? [
                                          ...new Set([
                                            ...selectedRows,
                                            ...pageAnimals.map((a) => a.id),
                                          ]),
                                        ]
                                      : selectedRows.filter(
                                          (id) =>
                                            !pageAnimals.some(
                                              (a) => a.id === id,
                                            ),
                                        ),
                                  )
                                }
                              />
                            </th>
                            <th>
                              <button
                                className="table-sort"
                                onClick={() => setSortAsc(!sortAsc)}
                              >
                                Cow tag<span>{sortAsc ? "↑" : "↓"}</span>
                              </button>
                            </th>
                            <th>Herd</th>
                            <th>Last assessment</th>
                            <th>Last observed</th>
                            <th aria-label="Details" />
                          </tr>
                        </thead>
                        <tbody>
                          {pageAnimals.map((a) => (
                            <tr key={a.id}>
                              <td className="checkbox-cell">
                                <input
                                  type="checkbox"
                                  aria-label={`Select Cow ${a.tag}`}
                                  checked={selectedRows.includes(a.id)}
                                  onChange={(e) =>
                                    setSelectedRows(
                                      e.target.checked
                                        ? [...selectedRows, a.id]
                                        : selectedRows.filter(
                                            (id) => id !== a.id,
                                          ),
                                    )
                                  }
                                />
                              </td>
                              <td>
                                <button
                                  className="cow-table-link"
                                  onClick={() => openAnimal(a)}
                                >
                                  <span className="cow-avatar">
                                    <CowMark size={20} />
                                  </span>
                                  <div>
                                    <strong>Cow {a.tag}</strong>
                                    <span>
                                      {a.id.startsWith("local-")
                                        ? "Locally added"
                                        : "Demo tag association"}
                                    </span>
                                  </div>
                                </button>
                              </td>
                              <td>
                                {
                                  data.herds.find((h) => h.id === a.herdId)
                                    ?.name
                                }
                              </td>
                              <td>
                                <StatusBadge status={a.assessment} />
                              </td>
                              <td className="table-muted">
                                {a.observedAt
                                  ? `Today, ${time(a.observedAt)}`
                                  : "No observation yet"}
                              </td>
                              <td>
                                <button
                                  className="icon-button"
                                  onClick={() => openAnimal(a)}
                                  aria-label={`Open Cow ${a.tag}`}
                                >
                                  <ChevronRight size={17} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {!filteredAnimals.length && (
                      <div className="table-empty">
                        <Search size={28} />
                        <h3>No cattle match those filters</h3>
                        <p>Try another tag, herd, or assessment.</p>
                        <button
                          className="secondary-button"
                          onClick={() => {
                            setQuery("");
                            setHerdFilter("all");
                            setStatusFilter("all");
                          }}
                        >
                          Clear filters
                        </button>
                      </div>
                    )}
                    <div className="table-footer">
                      <span>
                        {filteredAnimals.length
                          ? `${(page - 1) * 12 + 1}–${Math.min(page * 12, filteredAnimals.length)}`
                          : "0"}{" "}
                        of {filteredAnimals.length} cattle
                        {selectedRows.length
                          ? ` · ${selectedRows.length} selected`
                          : ""}
                      </span>
                      <div>
                        <button
                          className="icon-button"
                          disabled={page <= 1}
                          onClick={() => setPage((p) => p - 1)}
                          aria-label="Previous page"
                        >
                          <ArrowLeft size={16} />
                        </button>
                        <span>
                          Page {page} of {totalPages}
                        </span>
                        <button
                          className="icon-button"
                          disabled={page >= totalPages}
                          onClick={() => setPage((p) => p + 1)}
                          aria-label="Next page"
                        >
                          <ArrowRight size={16} />
                        </button>
                      </div>
                    </div>
                  </section>
                )}
                {section === "flights" && (
                  <>
                    <div className="flight-summary-grid">
                      <div className="card summary-stat">
                        <span>
                          <Plane size={17} />
                          Completed sweeps
                        </span>
                        <strong>{data.flights.length}</strong>
                        <small>Demo snapshot · November 14</small>
                      </div>
                      <div className="card summary-stat">
                        <span>
                          <Eye size={17} />
                          Latest cattle observed
                        </span>
                        <strong>
                          82 <em>/ 90</em>
                        </strong>
                        <small>8 cattle not observed</small>
                      </div>
                      <div className="card summary-stat">
                        <span>
                          <MapPin size={17} />
                          Latest coverage
                        </span>
                        <strong>
                          91<em>%</em>
                        </strong>
                        <small>Not a full census</small>
                      </div>
                    </div>
                    <section className="card flight-list">
                      <div className="card-title">
                        <h2>
                          Flight history{" "}
                          <span className="count-pill">{flights.length}</span>
                        </h2>
                        <button
                          className="primary-button"
                          onClick={() => {
                            setFormError("");
                            setFlightName("");
                            setModal("plan-flight");
                          }}
                        >
                          <Plus size={15} />
                          Plan a flight
                        </button>
                      </div>
                      {flights.map((f) => (
                        <button
                          className="flight-row"
                          key={f.id}
                          onClick={() => setSelectedFlight(f)}
                        >
                          <span
                            className={`flight-icon ${f.status === "planned" ? "planned-icon" : ""}`}
                          >
                            <Plane size={22} />
                          </span>
                          <span className="flight-name">
                            <strong>{f.name}</strong>
                            <span>
                              {f.drone} ·{" "}
                              {f.status === "planned"
                                ? "Local flight plan"
                                : `Today, ${time(f.startedAt)} · ${f.durationMinutes} min`}
                            </span>
                          </span>
                          <span
                            className={`flight-state ${f.status === "planned" ? "state-planned" : ""}`}
                          >
                            {f.status === "planned" ? "Planned" : "Completed"}
                          </span>
                          <span className="flight-coverage">
                            {f.coveragePercent === null
                              ? "—"
                              : `${f.coveragePercent}%`}
                            <small>coverage</small>
                          </span>
                          <ChevronRight size={18} />
                        </button>
                      ))}
                    </section>
                  </>
                )}
              </>
            )}
          </>
        )}
      </main>

      {toast && (
        <div className="toast" role="status">
          <Check size={17} />
          <span>{toast}</span>
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            <X size={15} />
          </button>
        </div>
      )}

      {animal && data && (
        <Dialog
          title={`Cow ${animal.tag}`}
          subtitle={`${data.herds.find((h) => h.id === animal.herdId)?.name} · ANIMAL DETAILS`}
          drawer
          onClose={closeAnimal}
        >
          <div className="animal-detail-heading">
            <span className="large-cow-avatar">
              <CowMark size={40} />
            </span>
            <div>
              <StatusBadge status={animal.assessment} />
              <p>
                {animal.observedAt
                  ? `Last observed today, ${time(animal.observedAt)}`
                  : "Awaiting first observation"}
              </p>
            </div>
          </div>
          <button
            className={`favorite-detail-toggle ${local.favoriteIds.includes(animal.id) ? "is-favorite" : ""}`}
            onClick={() => toggleFavorite(animal.id)}
            aria-pressed={local.favoriteIds.includes(animal.id)}
          >
            <Star
              size={15}
              fill={
                local.favoriteIds.includes(animal.id) ? "currentColor" : "none"
              }
            />
            {local.favoriteIds.includes(animal.id)
              ? "In Spotlight · click to remove"
              : "Add to Spotlight"}
          </button>
          <div className="detail-tabs">
            <button
              className={detailTab === "summary" ? "tab-active" : ""}
              onClick={() => setDetailTab("summary")}
            >
              Observation
            </button>
            <button
              className={detailTab === "history" ? "tab-active" : ""}
              onClick={() => setDetailTab("history")}
            >
              Review history
              {detailHistory.length > 0 && <span>{detailHistory.length}</span>}
            </button>
          </div>
          {detailTab === "summary" ? (
            <>
              <section className="detail-section">
                <div className="eyebrow">LATEST ASSESSMENT</div>
                <h3>
                  {animalAlert?.title ??
                    (animal.assessment === "unobserved"
                      ? "No observation available"
                      : "No clear deviation observed")}
                </h3>
                <p>
                  {animalAlert?.description ??
                    (animal.assessment === "unobserved"
                      ? "This animal is in the roster but has no captured observation in this snapshot. No health or location conclusion can be drawn."
                      : "The demo observation did not meet the review threshold. This is not a clinical health assessment.")}
                </p>
                <div className="detail-metric">
                  <span>{animal.metric}</span>
                  <strong>{animal.metricValue}</strong>
                </div>
                <div className="detail-facts">
                  <div>
                    <span>Source model</span>
                    <strong>{animal.modelVersion}</strong>
                  </div>
                  <div>
                    <span>Score scale</span>
                    <strong>Synthetic demo scale</strong>
                  </div>
                  <div>
                    <span>Model confidence</span>
                    <strong>
                      {animalAlert?.confidence != null
                        ? `${Math.round(animalAlert.confidence * 100)} / 100 · uncalibrated`
                        : "Not supplied"}
                    </strong>
                  </div>
                  <div>
                    <span>Location</span>
                    <strong>
                      {animal.mapPosition
                        ? "Illustrative map position"
                        : "Not observed"}
                    </strong>
                  </div>
                </div>
              </section>
              {animalAlert && (
                <section className="review-section">
                  <div className="review-title">
                    <h3>Human review</h3>
                    <span
                      className={`lifecycle lifecycle-${animalAlert.lifecycle}`}
                    >
                      {animalAlert.lifecycle === "invalidated"
                        ? "Rejected"
                        : animalAlert.lifecycle === "resolved"
                          ? "Reviewed"
                          : animalAlert.lifecycle === "acknowledged"
                            ? "Acknowledged"
                            : "Not reviewed"}
                    </span>
                  </div>
                  <label htmlFor="review-note">Review note</label>
                  <textarea
                    id="review-note"
                    rows={3}
                    maxLength={2000}
                    placeholder="What did you observe? Add context for the next reviewer…"
                    value={reviewNote}
                    onChange={(e) => {
                      setReviewNote(e.target.value);
                      setReviewError("");
                    }}
                    disabled={busy}
                  />
                  {reviewError && (
                    <p className="form-error" role="alert">
                      {reviewError}
                    </p>
                  )}
                  <div className="review-buttons">
                    <button
                      className="primary-button"
                      disabled={busy}
                      onClick={() => void review("accept")}
                    >
                      {busy ? (
                        <Loader2 size={15} className="spin" />
                      ) : (
                        <CheckCheck size={15} />
                      )}
                      Mark reviewed
                    </button>
                    <button
                      className="secondary-button"
                      disabled={busy}
                      onClick={() => void review("reject")}
                    >
                      Reject finding
                    </button>
                  </div>
                  <button
                    className="text-button acknowledge-button"
                    disabled={busy || animalAlert.lifecycle === "acknowledged"}
                    onClick={() => void review("acknowledge")}
                  >
                    <Bell size={14} />
                    {animalAlert.lifecycle === "acknowledged"
                      ? "Acknowledged for follow-up"
                      : "Acknowledge for follow-up"}
                  </button>
                  <p className="demo-write-note">
                    Demo reviews are saved in this browser. They do not change
                    live ranch records.
                  </p>
                </section>
              )}
              <button
                className="secondary-button full-width"
                onClick={() => {
                  setHerdFilter(animal.herdId);
                  setSection("map");
                  setSelectedAnimal(null);
                }}
              >
                <MapPin size={15} />
                Open herd on map
                <ArrowUpRight size={14} />
              </button>
            </>
          ) : (
            <section className="detail-section">
              <div className="history-entry">
                <span className="history-dot" />
                <div>
                  <strong>Demo finding recorded</strong>
                  <p>
                    {time(animal.observedAt)} · {animal.modelVersion}
                  </p>
                </div>
              </div>
              {detailHistory.map((r, i) => (
                <div className="history-entry" key={`${r.alertId}-${i}`}>
                  <span className="history-dot history-reviewed" />
                  <div>
                    <strong>
                      {r.action === "reject"
                        ? "Finding rejected"
                        : r.action === "accept"
                          ? "Marked reviewed"
                          : "Acknowledged"}
                    </strong>
                    <p>{r.reason}</p>
                    <small>
                      {r.actor} · {time(r.recordedAt)} · local demo change
                    </small>
                  </div>
                </div>
              ))}
              {!detailHistory.length && (
                <p className="muted">
                  No human review has been recorded in this browser.
                </p>
              )}
            </section>
          )}
        </Dialog>
      )}

      {selectedFlight && (
        <Dialog
          title={selectedFlight.name}
          subtitle="FLIGHT DETAILS"
          onClose={closeFlight}
        >
          <div className="flight-dialog-status">
            <span
              className={`flight-state ${selectedFlight.status === "planned" ? "state-planned" : ""}`}
            >
              {selectedFlight.status === "planned" ? "Local plan" : "Completed"}
            </span>
            <span>{selectedFlight.drone}</span>
          </div>
          {selectedFlight.status === "planned" ? (
            <div className="info-panel">
              <CalendarDays size={22} />
              <p>
                This flight plan is saved in this browser only. No drone command
                or scheduling request has been sent.
              </p>
            </div>
          ) : (
            <>
              <div className="flight-detail-stats">
                <div>
                  <span>Flight time</span>
                  <strong>{selectedFlight.durationMinutes} min</strong>
                </div>
                <div>
                  <span>Cows observed</span>
                  <strong>{selectedFlight.observedAnimals}</strong>
                </div>
                <div>
                  <span>Coverage</span>
                  <strong>{selectedFlight.coveragePercent}%</strong>
                </div>
              </div>
              <section className="detail-section">
                <h3>Capture & processing</h3>
                <div className="pipeline-step">
                  <Check size={16} />
                  <div>
                    <strong>Clips received</strong>
                    <p>
                      {selectedFlight.clips} demo cow clips · 10–15 seconds at
                      30 fps
                    </p>
                  </div>
                </div>
                <div className="pipeline-step">
                  <Check size={16} />
                  <div>
                    <strong>Model analysis complete</strong>
                    <p>Locomotion and estrus behavior models</p>
                  </div>
                </div>
                <div className="pipeline-step">
                  <Activity size={16} />
                  <div>
                    <strong>{activeAlerts.length} findings await review</strong>
                    <p>Predictions are not confirmed diagnoses</p>
                  </div>
                </div>
              </section>
            </>
          )}
          <button
            className="primary-button full-width"
            onClick={() => {
              setSelectedFlight(null);
              setSection("map");
              setHerdFilter("all");
            }}
          >
            <Map size={16} />
            Open pasture map
          </button>
        </Dialog>
      )}

      {modal === "about" && (
        <Dialog
          title="A working view of your herd"
          subtitle="DEMO WORKSPACE"
          onClose={closeModal}
        >
          <div className="info-panel">
            <span className="healthy-dot" />
            <p>
              You’re exploring sample cattle, flights and observations. Live
              ranch data is not connected.
            </p>
          </div>
          <p className="dialog-copy">
            Open an alert, review a finding, filter a herd, or explore the map.
            Reviews, added cattle and flight plans stay in this browser until
            you reset the demo.
          </p>
          <div className="detail-facts">
            <div>
              <span>Snapshot</span>
              <strong>November 14 · 8:42 AM Pacific</strong>
            </div>
            <div>
              <span>Map background</span>
              <strong>Illustrative · not georeferenced</strong>
            </div>
            <div>
              <span>Health indicators</span>
              <strong>Unconfirmed model observations</strong>
            </div>
          </div>
          <button className="primary-button full-width" onClick={closeModal}>
            Explore the herd
            <ArrowRight size={15} />
          </button>
        </Dialog>
      )}
      {modal === "ranch" && (
        <Dialog
          title={data?.ranch ?? "North Creek Ranch"}
          subtitle="CURRENT WORKSPACE"
          onClose={closeModal}
        >
          <div className="ranch-illustration">
            <CowMark size={55} />
          </div>
          <p className="dialog-copy">
            Your demo ranch has two managed herds and two pasture areas. Select
            a herd to explore its cattle.
          </p>
          {data?.herds.map((h) => (
            <button
              key={h.id}
              className="pasture-list-item"
              onClick={() => {
                setHerdFilter(h.id);
                setStatusFilter("all");
                setSection("cattle");
                closeModal();
              }}
            >
              <div>
                <strong>{h.name}</strong>
                <span>{h.pasture}</span>
              </div>
              <ChevronRight size={17} />
            </button>
          ))}
        </Dialog>
      )}
      {modal === "settings" && (
        <Dialog
          title="Workspace settings"
          subtitle="YOUR PREFERENCES"
          onClose={closeModal}
        >
          <div className="settings-row">
            <div>
              <strong>Show pasture boundaries</strong>
              <p>Display herd areas on the illustrative map.</p>
            </div>
            <button
              role="switch"
              aria-checked={local.preferences.boundaries}
              aria-label="Show pasture boundaries"
              className={`toggle ${local.preferences.boundaries ? "toggle-on" : ""}`}
              onClick={() =>
                setLocal((s) => ({
                  ...s,
                  preferences: {
                    ...s.preferences,
                    boundaries: !s.preferences.boundaries,
                  },
                }))
              }
            >
              <span />
            </button>
          </div>
          <div className="settings-row">
            <div>
              <strong>Observation freshness</strong>
              <p>Count observations older than this interval.</p>
            </div>
            <select
              className="field-select"
              aria-label="Observation freshness threshold"
              value={local.preferences.staleMinutes}
              onChange={(e) =>
                setLocal((s) => ({
                  ...s,
                  preferences: {
                    ...s.preferences,
                    staleMinutes: Number(e.target.value),
                  },
                }))
              }
            >
              <option value="30">30 minutes</option>
              <option value="60">1 hour</option>
              <option value="120">2 hours</option>
            </select>
          </div>
          <p className="dialog-copy">
            {data
              ? animals.filter(
                  (a) =>
                    a.observedAt &&
                    (new Date(data.referenceNow).getTime() -
                      new Date(a.observedAt).getTime()) /
                      60000 >
                      local.preferences.staleMinutes,
                ).length
              : 0}{" "}
            demo observations exceed this interval at the snapshot time.
          </p>
          <div className="settings-row">
            <div>
              <strong>Data source</strong>
              <p>Sample observations · stored locally</p>
            </div>
            <span className="demo-badge static-badge">
              <span />
              Demo
            </span>
          </div>
          <button
            className="secondary-button full-width"
            onClick={() => {
              closeModal();
              notify("Preferences saved for this browser.");
            }}
          >
            <Check size={15} />
            Done
          </button>
        </Dialog>
      )}
      {modal === "profile" && (
        <Dialog
          title="Demo operator"
          subtitle="WORKSPACE PROFILE"
          onClose={closeModal}
        >
          <div className="profile-summary">
            <span className="profile-large">JD</span>
            <div>
              <strong>Jordan Davis</strong>
              <span>Demo reviewer · North Creek Ranch</span>
            </div>
          </div>
          <p className="dialog-copy">
            This is a demonstration profile. No live ranch account or real user
            session is connected.
          </p>
          <p className="demo-write-note">Reset restores demo edits and the default Spotlight list. Attached video copies are managed separately from each cow’s recording viewer.</p>
          <div className="detail-facts">
            <div>
              <span>Local reviews</span>
              <strong>{local.reviews.length}</strong>
            </div>
            <div>
              <span>Locally added cattle</span>
              <strong>{local.animals.length}</strong>
            </div>
            <div>
              <span>Local flight plans</span>
              <strong>{local.flights.length}</strong>
            </div>
          </div>
          <button
            className="secondary-button full-width danger-text"
            onClick={() => {
              setLocal(emptyLocal);
              closeModal();
              setSelectedAnimal(null);
              setQuery("");
              setHerdFilter("all");
              setStatusFilter("all");
              notify("Demo changes reset. Original observations restored.");
            }}
          >
            <RotateCcw size={15} />
            Reset demo changes
          </button>
        </Dialog>
      )}
      {modal === "search" && (
        <Dialog
          title="Find your way around"
          subtitle="QUICK SEARCH"
          wide
          onClose={closeModal}
        >
          <div className="input-with-icon search-modal-input">
            <Search size={20} />
            <input
              autoFocus
              placeholder="Search cow tags, herds or flights…"
              aria-label="Search workspace"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <kbd>ESC</kbd>
          </div>
          <div className="search-results">
            {animals
              .filter((a) =>
                search.trim()
                  ? `cow ${a.tag}`.includes(search.toLowerCase().trim())
                  : ["718", "904", "652"].includes(a.tag),
              )
              .slice(0, 6)
              .map((a) => (
                <button
                  key={a.id}
                  onClick={() => {
                    closeModal();
                    openAnimal(a);
                  }}
                >
                  <span className="cow-avatar">
                    <CowMark size={20} />
                  </span>
                  <div>
                    <strong>Cow {a.tag}</strong>
                    <span>
                      {data?.herds.find((h) => h.id === a.herdId)?.name}
                    </span>
                  </div>
                  <StatusBadge status={a.assessment} />
                  <ChevronRight size={16} />
                </button>
              ))}
            {data?.herds
              .filter(
                (h) =>
                  !search ||
                  h.name.toLowerCase().includes(search.toLowerCase()) ||
                  h.pasture.toLowerCase().includes(search.toLowerCase()),
              )
              .map((h) => (
                <button
                  key={h.id}
                  onClick={() => {
                    closeModal();
                    setHerdFilter(h.id);
                    setSection("cattle");
                    setQuery("");
                    setStatusFilter("all");
                  }}
                >
                  <span className="cow-avatar">
                    <Map size={19} />
                  </span>
                  <div>
                    <strong>{h.name}</strong>
                    <span>{h.pasture}</span>
                  </div>
                  <ChevronRight size={16} />
                </button>
              ))}
            {flights
              .filter(
                (f) =>
                  search && f.name.toLowerCase().includes(search.toLowerCase()),
              )
              .map((f) => (
                <button
                  key={f.id}
                  onClick={() => {
                    closeModal();
                    setSelectedFlight(f);
                  }}
                >
                  <span className="cow-avatar">
                    <Plane size={20} />
                  </span>
                  <div>
                    <strong>{f.name}</strong>
                    <span>{f.drone}</span>
                  </div>
                  <ChevronRight size={16} />
                </button>
              ))}
            {search &&
              !animals.some((a) =>
                `cow ${a.tag}`.includes(search.toLowerCase().trim()),
              ) &&
              !data?.herds.some((h) =>
                `${h.name} ${h.pasture}`
                  .toLowerCase()
                  .includes(search.toLowerCase()),
              ) &&
              !flights.some((f) =>
                f.name.toLowerCase().includes(search.toLowerCase()),
              ) && (
                <div className="table-empty">
                  <h3>No matches yet</h3>
                  <p>Try a tag such as 718, or “Herd 1”.</p>
                </div>
              )}
          </div>
        </Dialog>
      )}
      {modal === "add-animal" && (
        <Dialog
          title="Add a cow"
          subtitle="DEMO CATTLE REGISTER"
          onClose={closeModal}
        >
          <form onSubmit={addAnimal} className="entry-form">
            <label htmlFor="cow-tag">Cow tag</label>
            <input
              id="cow-tag"
              inputMode="numeric"
              autoFocus
              maxLength={12}
              placeholder="e.g. 905"
              value={tag}
              onChange={(e) => {
                setTag(e.target.value);
                setFormError("");
              }}
              required
            />
            <label htmlFor="new-herd">Herd</label>
            <select
              id="new-herd"
              value={newHerd}
              onChange={(e) => setNewHerd(e.target.value)}
            >
              {data?.herds.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
            <p className="dialog-copy">
              New cattle start as unobserved. This adds a local demo record,
              with no assumed health status or location.
            </p>
            {formError && (
              <p className="form-error" role="alert">
                {formError}
              </p>
            )}
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={closeModal}
              >
                Cancel
              </button>
              <button className="primary-button" type="submit">
                <Plus size={15} />
                Add cow
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {modal === "plan-flight" && (
        <Dialog
          title="Plan a pasture check"
          subtitle="LOCAL FLIGHT PLAN"
          onClose={closeModal}
        >
          <form
            className="entry-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!flightName.trim()) {
                setFormError("Give this flight plan a name.");
                return;
              }
              const flight: Flight = {
                id: `local-${crypto.randomUUID()}`,
                name: flightName.trim(),
                drone: "Drone 01",
                startedAt: new Date().toISOString(),
                durationMinutes: 0,
                coveragePercent: null,
                observedAnimals: 0,
                batteryPercent: 0,
                status: "planned",
                clips: 0,
              };
              setLocal((s) => ({ ...s, flights: [flight, ...s.flights] }));
              closeModal();
              notify("Flight plan saved locally. No drone command was sent.");
            }}
          >
            <label htmlFor="flight-name">Flight name</label>
            <input
              id="flight-name"
              autoFocus
              maxLength={100}
              value={flightName}
              onChange={(e) => setFlightName(e.target.value)}
              placeholder="e.g. Afternoon pasture sweep"
              required
            />
            <div className="info-panel">
              <Plane size={22} />
              <p>
                Save a plan in this demo workspace. Scheduling and drone
                dispatch are not connected.
              </p>
            </div>
            {formError && <p className="form-error">{formError}</p>}
            <div className="form-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={closeModal}
              >
                Cancel
              </button>
              <button className="primary-button" type="submit">
                <CalendarDays size={15} />
                Save plan
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </div>
  );
}
