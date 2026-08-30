// Resource revision: v=0.8.0.44
class DeyeEnergyManagerCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this._interacting = false;
    this._pendingRender = false;
    this._lastScheduleSignature = "";
    this._scheduleEntityIds = [];
    this._dialog = null;
    this._chargeProfileDraft = {};
    this._chargeProfileGridDraft = null;
    this._chargeProfilePending = null;
    this._normalProfileDraft = {};
    this._normalProfilePending = null;
    this._touEditDraft = null;
    this._touEditOriginal = null;
    this._touSaving = false;
    this._touSaveError = "";
    this._touAwaitingConfirmation = null;
    this._lastTouDiagnosticsSignature = "";
    this._slotEditOriginal = null;
    this._slotEditDraft = null;
    this._slotSaving = false;
    this._slotSaveError = "";
    this._slotSaveMessage = "";
    this._slotDiscardPrompt = false;
    this._slotAwaitingRefresh = null;
    this._defaultSettingsDraft = {};
    this._scrollTops = {};
    this._pageScrollTops = [];
    this._interactionRelease = null;
    this._isRendered = false;
    this._optimisticStates = {};
    this._pendingSaves = 0;
    this._saveStatus = "idle";
    this._saveMessage = "";
    this._saveStatusTimer = null;
    this._saveHadError = false;
    this._controlTogglePending = false;
    this._controlError = "";
    this._controlExpectedEnabled = null;
    this._controlFeedbackActive = false;
    this._defaultsApplying = false;
    this._defaultsStatus = "idle";
    this._defaultsMessage = "";
    this._resumeApplying = false;
    this._selectionMode = false;
    this._selectedSlots = new Set();
    this._bulkEditDraft = null;
    this._bulkEditFields = null;
    this._bulkApplying = false;
    this._settingsTab = "defaults";
    this._historyFilters = { from: "", to: "", type: "all" };
    this._lastAiAnalysisCheck = 0;
    this._aiSettingsSaveTimer = null;
    this._aiSettingsSection = "general";
    this._aiProfileDraft = null;
    this._aiProfileStatus = "";
    this._aiDetailKey = null;
    this._aiApiDraft = null;
    this._aiApiMessage = "";
    this._updateFrame = null;
    this._lastSlowSignature = "";
    this._tariffDraft = null;
    this._tariffSaveStatus = "";
    this._aiView = "overview";
    this._aiDay = "today";
    this._aiExplanationDay = "today";
    this._aiShow24 = false;
    this._aiWeatherMode = "daily";
    this._aiChartPinned = null;
    this._aiChartHiddenSeries = new Set();
    this._aiSelections = { today: new Set(), tomorrow: new Set() };
    this._aiExecutionRange = "today";
    this._aiExecutionDate = "";
    this._aiExecutionData = null;
    this._aiExecutionLoading = false;
    this._aiExecutionError = "";
  }

  layoutConfig() {
    const cfg = this.config?.layout || {};
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const asBool = (value, fallback) => (typeof value === "boolean" ? value : fallback);
    const asNumber = (value, fallback, min, max) => {
      const num = Number(value);
      return Number.isFinite(num) ? clamp(num, min, max) : fallback;
    };
    const asString = (value, fallback, allowed) => {
      const str = String(value || fallback).trim();
      return allowed.includes(str) ? str : fallback;
    };
    const defaults = {
      layout_mode: "auto",
      dashboard_width: 1280,
      max_scale: 1,
      min_scale: 0.2,
      center_dashboard: true,
      fit_to_width: false,
      allow_horizontal_scroll: false,
      grid_columns: null,
      grid_gap: 16,
      section: null,
      sections: {
        status_energy: true,
        prices: true,
        solcast: true,
        schedule: true,
        sales_stats: true,
      },
      mobile: {
        mode: "auto",
        preserve_desktop_layout: false,
        fit_to_width: true,
        allow_horizontal_scroll: false,
        grid_columns: 1,
        mobile_breakpoint: 768,
      },
      prices_ratio: 0.80,
      buy_prices_ratio: 0.80,
      solcast_ratio: 1.40,
      energy_tile_width: 300,
      energy_tile_gap: 28,
      inverter_scale: 1,
      flow_animation_speed: 6,
    };
    const mobileDefaults = defaults.mobile;
    const mobile = {
      mode: asString(cfg.mobile?.mode, mobileDefaults.mode, ["auto", "full", "section", "single", "grid", "fit"]),
      preserve_desktop_layout: asBool(cfg.mobile?.preserve_desktop_layout, mobileDefaults.preserve_desktop_layout),
      fit_to_width: asBool(cfg.mobile?.fit_to_width, mobileDefaults.fit_to_width),
      allow_horizontal_scroll: asBool(cfg.mobile?.allow_horizontal_scroll, mobileDefaults.allow_horizontal_scroll),
      grid_columns: asNumber(cfg.mobile?.grid_columns, mobileDefaults.grid_columns, 1, 4),
      mobile_breakpoint: asNumber(cfg.mobile?.mobile_breakpoint, mobileDefaults.mobile_breakpoint, 320, 1600),
    };
    return {
      layout_mode: asString(cfg.layout_mode, defaults.layout_mode, ["auto", "full", "section", "single", "grid", "fit"]),
      dashboard_width: asNumber(cfg.dashboard_width, defaults.dashboard_width, 320, 2400),
      max_scale: asNumber(cfg.max_scale, defaults.max_scale, 0.2, 3),
      min_scale: asNumber(cfg.min_scale, defaults.min_scale, 0.1, 1),
      center_dashboard: asBool(cfg.center_dashboard, defaults.center_dashboard),
      fit_to_width: asBool(cfg.fit_to_width, defaults.fit_to_width),
      allow_horizontal_scroll: asBool(cfg.allow_horizontal_scroll, defaults.allow_horizontal_scroll),
      grid_columns: cfg.grid_columns === null || cfg.grid_columns === undefined ? defaults.grid_columns : asNumber(cfg.grid_columns, defaults.grid_columns, 1, 6),
      grid_gap: asNumber(cfg.grid_gap, defaults.grid_gap, 0, 64),
      section: asString(cfg.section, defaults.section, ["status_energy", "prices", "solcast", "schedule", "sales_stats", "ai", "settings"]),
      sections: {
        status_energy: asBool(cfg.sections?.status_energy, defaults.sections.status_energy),
        prices: asBool(cfg.sections?.prices, defaults.sections.prices),
        solcast: asBool(cfg.sections?.solcast, defaults.sections.solcast),
        schedule: asBool(cfg.sections?.schedule, defaults.sections.schedule),
        sales_stats: asBool(cfg.sections?.sales_stats, defaults.sections.sales_stats),
      },
      mobile,
      prices_ratio: asNumber(cfg.prices_ratio, defaults.prices_ratio, 0.1, 5),
      buy_prices_ratio: asNumber(cfg.buy_prices_ratio, defaults.buy_prices_ratio, 0.1, 5),
      solcast_ratio: asNumber(cfg.solcast_ratio, defaults.solcast_ratio, 0.1, 5),
      energy_tile_width: asNumber(cfg.energy_tile_width, defaults.energy_tile_width, 120, 360),
      energy_tile_gap: asNumber(cfg.energy_tile_gap, defaults.energy_tile_gap, 0, 100),
      inverter_scale: asNumber(cfg.inverter_scale, defaults.inverter_scale, 0.5, 2),
      flow_animation_speed: asNumber(cfg.flow_animation_speed, defaults.flow_animation_speed, 1, 20),
    };
  }

  isMobileLayout(layout) {
    const viewportWidth = window.innerWidth || 0;
    const hostWidth = this.clientWidth || this.getBoundingClientRect?.().width || 0;
    const width = hostWidth > 0 && viewportWidth > 0 ? Math.min(hostWidth, viewportWidth) : (hostWidth || viewportWidth);
    return width > 0 && width <= layout.mobile.mobile_breakpoint;
  }

  effectiveLayout() {
    const layout = this.layoutConfig();
    const isMobile = this.isMobileLayout(layout) && !layout.mobile.preserve_desktop_layout;
    layout.is_mobile = isMobile;
    if (isMobile) {
      const mobileMode = layout.mobile.mode;
      if (mobileMode !== "auto") {
        layout.layout_mode = mobileMode;
      }
      layout.fit_to_width = layout.mobile.fit_to_width;
      layout.allow_horizontal_scroll = layout.mobile.allow_horizontal_scroll;
      if (layout.mobile.grid_columns !== null && layout.mobile.grid_columns !== undefined) {
        layout.grid_columns = layout.mobile.grid_columns;
      }
    }
    if (layout.layout_mode === "full") {
      layout.fit_to_width = true;
      layout.center_dashboard = false;
    } else if (layout.layout_mode === "fit") {
      layout.fit_to_width = true;
      layout.center_dashboard = true;
    }
    return layout;
  }

  getGridOptions() {
    return {
      columns: "full",
      min_columns: 3,
    };
  }

  connectedCallback() {
    if (!this._dialogCloseHandler) {
      this._dialogCloseHandler = (event) => {
        const target = event.target instanceof Element ? event.target : null;
        const closeControl = target?.closest("[data-close-dialog]");
        if (!closeControl || !this.contains(closeControl)) return;
        if (closeControl.classList.contains("overlay") && target !== closeControl) return;
        event.preventDefault();
        event.stopPropagation();
        this.closeDialog();
      };
      this.addEventListener("click", this._dialogCloseHandler);
    }
    if (!this._dialogEscapeHandler) {
      this._dialogEscapeHandler = (event) => {
        if (event.key === "Escape" && this._dialog) this.closeDialog();
      };
      this.ownerDocument?.addEventListener("keydown", this._dialogEscapeHandler);
    }
    this.addEventListener("wheel", () => this.holdInteraction(900), { passive: true });
    this.addEventListener("touchstart", () => this.holdInteraction(1300), { passive: true });
    this.addEventListener("touchmove", () => this.holdInteraction(1300), { passive: true });
    if (!this._flowResizeHandler) {
      this._flowResizeHandler = () => this.scaleFlowPanel();
      window.addEventListener("resize", this._flowResizeHandler);
      window.setTimeout(() => this.scaleFlowPanel(), 100);
    }
    if (!this._flowResizeObserver && typeof ResizeObserver !== "undefined") {
      this._flowResizeObserver = new ResizeObserver((entries) => {
        const width = entries[0]?.contentRect?.width || 0;
        if (!width || Math.abs(width - (this._flowObservedWidth || 0)) < 0.5) return;
        this._flowObservedWidth = width;
        this.scaleFlowPanel();
      });
    }
    this.addEventListener("focusin", () => {
      window.clearTimeout(this._interactionRelease);
      this._interacting = true;
    });
    this.addEventListener("focusout", () => this.releaseInteraction(350));
  }

  disconnectedCallback() {
    if (this._updateFrame) cancelAnimationFrame(this._updateFrame);
    if (this._flowResizeHandler) {
      window.removeEventListener("resize", this._flowResizeHandler);
      this._flowResizeHandler = null;
    }
    this._flowResizeObserver?.disconnect();
    this._flowResizeObserver = null;
    this._flowObservedWrapper = null;
    this._flowObservedWidth = 0;
    if (this._dialogEscapeHandler) {
      this.ownerDocument?.removeEventListener("keydown", this._dialogEscapeHandler);
      this._dialogEscapeHandler = null;
    }
  }

  closeDialog() {
    if (!this._dialog) return;
    if (this.isScheduleSlotDialog()) {
      if (this._slotSaving) return false;
      if (this.slotEditDirty() && !this._slotDiscardPrompt) {
        this._slotDiscardPrompt = true;
        this.renderDialogOnly();
        return false;
      }
      this.resetSlotEditor();
    }
    if (this._dialog.type === "tou") this.resetTouEditor();
    this._dialog = null;
    this._interacting = false;
    this.render();
    return true;
  }

  set hass(hass) {
    this._hass = hass;
    this.syncSlotEditorAfterHass();
    if (this._isRendered) {
      const touSignature = this.touDiagnosticsSignature();
      if (touSignature !== this._lastTouDiagnosticsSignature) {
        this._lastTouDiagnosticsSignature = touSignature;
        this.syncTouEditorAfterDiagnostics();
        if (this._dialog?.type === "tou" || (this._dialog?.type === "settings" && this._settingsTab === "tou")) {
          this.renderDialogOnly();
        }
      }
      const scheduleSignature = this.scheduleStateSignature();
      if (scheduleSignature !== this._lastScheduleSignature) {
        if (this.requestScheduleRender()) return;
      }
      if (this._updateFrame) cancelAnimationFrame(this._updateFrame);
      this._updateFrame = requestAnimationFrame(() => {
        this._updateFrame = null;
        this.updateDynamicValues();
      });
      return;
    }
    this.render(true);
  }

  getCardSize() {
    return 12;
  }

  isInteracting() {
    const active = this.ownerDocument?.activeElement;
    return this._interacting || (active && this.contains(active));
  }

  releaseInteraction(delay = 350) {
    window.clearTimeout(this._interactionRelease);
    this._interactionRelease = window.setTimeout(() => {
      this._interacting = false;
      this.flushPendingRender();
    }, delay);
  }

  holdInteraction(delay = 850) {
    this._interacting = true;
    this.releaseInteraction(delay);
  }

  requestScheduleRender() {
    if (this.isInteracting()) {
      this._pendingRender = true;
      return false;
    }
    this._pendingRender = false;
    this.captureScrollPositions();
    this.render();
    return true;
  }

  flushPendingRender() {
    if (!this._pendingRender || this.isInteracting()) return false;
    this._pendingRender = false;
    this.captureScrollPositions();
    this.render();
    return true;
  }

  captureScrollPositions() {
    this.querySelectorAll("[data-scroll-key]").forEach((el) => {
      this._scrollTops[el.dataset.scrollKey] = el.scrollTop;
    });
    this._pageScrollTops = this.pageScrollContainers().map((el) => ({
      el,
      top: el.scrollTop,
      left: el.scrollLeft,
    }));
  }

  pageScrollContainers() {
    const containers = [];
    const seen = new Set();
    const add = (el) => {
      if (!el || seen.has(el)) return;
      seen.add(el);
      const canScrollY = (el.scrollHeight || 0) - (el.clientHeight || 0) > 1;
      const canScrollX = (el.scrollWidth || 0) - (el.clientWidth || 0) > 1;
      if (canScrollY || canScrollX) containers.push(el);
    };

    add(document.scrollingElement);
    add(document.documentElement);
    add(document.body);

    let node = this;
    while (node) {
      if (node.nodeType === 1) add(node);
      if (node.assignedSlot) {
        node = node.assignedSlot;
      } else if (node.parentNode) {
        node = node.parentNode;
      } else {
        const root = node.getRootNode?.();
        node = root?.host || null;
      }
    }
    return containers;
  }

  restorePageScrollPositions() {
    const restore = () => {
      (this._pageScrollTops || []).forEach(({ el, top, left }) => {
        if (!el) return;
        try {
          el.scrollTop = top;
          el.scrollLeft = left;
        } catch (_err) {
          // Some Home Assistant containers are read-only during view transitions.
        }
      });
    };
    restore();
    requestAnimationFrame(restore);
    window.setTimeout(restore, 0);
  }

  restoreScrollPositions() {
    this.querySelectorAll("[data-scroll-key]").forEach((el) => {
      const key = el.dataset.scrollKey;
      if (this._scrollTops[key] !== undefined) el.scrollTop = this._scrollTops[key];
      this.attachScrollHandlers(el);
    });
    this.restorePageScrollPositions();
  }

  attachScrollHandlers(el) {
    if (!el || el._demScrollBound) return;
    el._demScrollBound = true;
    el.addEventListener("scroll", () => {
      this._scrollTops[el.dataset.scrollKey] = el.scrollTop;
      this.holdInteraction(900);
    }, { passive: true });
    el.addEventListener("wheel", () => this.holdInteraction(900), { passive: true });
    el.addEventListener("touchstart", () => this.holdInteraction(1200), { passive: true });
    el.addEventListener("touchmove", () => this.holdInteraction(1200), { passive: true });
    el.addEventListener("pointerenter", () => this.holdInteraction(900));
    el.addEventListener("pointerleave", () => this.releaseInteraction(350));
  }

  setText(selector, value) {
    const el = this.querySelector(selector);
    if (el && el.textContent !== String(value)) {
      el.textContent = value;
      el.classList.remove("live-changed");
      void el.offsetWidth;
      el.classList.add("live-changed");
    }
  }

  setHtml(selector, value) {
    const el = this.querySelector(selector);
    if (el) el.innerHTML = value;
  }

  setClass(selector, baseClass, activeClass, isActive) {
    const el = this.querySelector(selector);
    if (!el) return;
    el.className = `${baseClass}${isActive ? ` ${activeClass}` : ""}`;
  }

  updateDynamicValues() {
    if (!this._hass || !this._isRendered) return;
    this.checkChargeProfilePending();
    this.checkNormalProfilePending();
    this.updateControlUi();
    const slots = this.scheduleSlots();
    const statusEntity = this.entity("sensor", "manager_status");
    const activeSlotEntity = this.entity("sensor", "active_slot");
    const rawStatus = this.state(statusEntity);
    const [modeText, modeClass] = this.readMode(rawStatus);
    const activeSlot = this.state(activeSlotEntity);
    const activeSlotLabel = (slots.find(([key]) => key === activeSlot)?.[1] || activeSlot).replace(/:00/g, "");
    const batterySoc = this.entity("sensor", "battery_soc");
    const soldEnergyToday = this.entity("sensor", "sold_energy_today");
    const soldValueToday = this.entity("sensor", "sold_value_today");
    const sellPriceToday = this.entity("sensor", ["sell_price_today", "energy_price"]);
    const sellPriceTomorrow = this.entity("sensor", "sell_price_tomorrow");
    const buyPriceToday = this.entity("sensor", "buy_price_today");
    const buyPriceTomorrow = this.entity("sensor", "buy_price_tomorrow");
    const solcastPower = this.entity("sensor", "solcast_current_power");
    const solcastToday = this.entity("sensor", "solcast_forecast_today");
    const solcastTomorrow = this.entity("sensor", "solcast_forecast_tomorrow");
    const solcastDay3 = this.entity("sensor", "solcast_forecast_day_3");
    const solcastDay4 = this.entity("sensor", "solcast_forecast_day_4");
    const solcastDay5 = this.entity("sensor", "solcast_forecast_day_5");
    const solcastDay6 = this.entity("sensor", "solcast_forecast_day_6");
    const solcastDay7 = this.entity("sensor", "solcast_forecast_day_7");
    const solcastRemaining = this.entity("sensor", "solcast_remaining_today");
    const solcastPeakPower = this.entity("sensor", "solcast_peak_power_today");
    const solcastPeakTime = this.entity("sensor", "solcast_peak_time_today");
    const dailyPvProduction = this.entity("sensor", "daily_pv_production");
    const solcastAccuracy = this.entity("sensor", "solcast_accuracy");
    const minSellPrice = this.entity("number", "minimum_sell_price");
    const priceThreshold = this.asNumber(this.numberState(minSellPrice, 0)) || 0;
    const scheduler = this.entity("switch", "scheduler");
    const controlMode = this.entity("select", "control_mode");
    const lastAction = this.state(this.entity("sensor", "last_action"), "");
    const decisionText = this.state(this.entity("sensor", "decision_reason"));
    const statusUpper = String(rawStatus || "").toUpperCase();
    const lastActionUpper = String(lastAction || "").toUpperCase();
    const schedulerOn = this.state(scheduler) === "on";
    const defaultsActive = statusUpper.includes("DEFAULT") || statusUpper.includes("PRICE") || statusUpper.includes("SOC") || (!schedulerOn && lastActionUpper.includes("DEFAULT"));
    const sellActive = schedulerOn && statusUpper.includes("SCHEDULE") && !defaultsActive;
    const stopActive = statusUpper.includes("STOP") || this.state(controlMode) === "Stop Sell" || (!schedulerOn && (statusUpper.includes("IDLE") || lastActionUpper.includes("RESTORED") || lastActionUpper.includes("STOP")));
    const defaultButtonActive = defaultsActive && !stopActive;
    const analysisNow = Date.now();
    if (this.aiSettings().enabled && analysisNow - this._lastAiAnalysisCheck >= 900000) {
      this._lastAiAnalysisCheck = analysisNow;
      this.saveAiAnalysis(this.aiSuggestions(slots));
    }

    const pvValue = this.asNumber(this.state(this.entity("sensor", "pv_power")), 0) || 0;
    const gridValue = this.asNumber(this.state(this.entity("sensor", "grid_power")), 0) || 0;
    const batteryValue = this.asNumber(this.state(this.entity("sensor", "battery_power")), 0) || 0;
    const loadValue = this.asNumber(this.state(this.entity("sensor", "load_power")), 0) || 0;
    const batterySocValue = this.optionalSocNumber(this.state(this.entity("sensor", "battery_soc")));
    const currentModeValue = this.deyeWorkModeState();

    const formatKw = (w) => {
      if (w === null || w === undefined || Number.isNaN(w)) return "—";
      return Math.abs(w) >= 1000 ? `${(w / 1000).toFixed(2)} kW` : `${Math.round(w)} W`;
    };
    const gridMainText = gridValue < -1 ? `Eksport ${formatKw(Math.abs(gridValue))}` : gridValue > 1 ? `Pobór ${formatKw(gridValue)}` : `Bilans 0 kW`;
    const batteryDirectionText = batteryValue < -1 ? `Ładowanie ${formatKw(Math.abs(batteryValue))}` : batteryValue > 1 ? `Rozładowanie ${formatKw(batteryValue)}` : `Spoczynek`;

    const fmtNum = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v)) ? "—" : v.toFixed(d);
    const detailed = (key, fallback = null) => this.asNumber(this.state(this.entity("sensor", key)), fallback);
    const managerModeClass = this.modeTextClass(modeText);
    const currentModeMeta = currentModeValue ? this.modeMeta(currentModeValue, true) : { cls: "disabled" };
    const safeModeClass = (cls) => cls ? `mode-${cls}` : "";

    this.setText("[data-live='pv-main']", formatKw(pvValue));
    this.setText("[data-live='pv-total']", formatKw(pvValue));
    this.setText("[data-live='pv-daily']", fmtNum(detailed("daily_pv_production"), 2));
    this.setText("[data-live='pv1-power']", formatKw(detailed("pv1_power")));
    this.setText("[data-live='pv1-volts']", fmtNum(detailed("pv1_voltage"), 1));
    this.setText("[data-live='pv1-amps']", fmtNum(detailed("pv1_current"), 1));
    this.setText("[data-live='pv2-power']", formatKw(detailed("pv2_power")));
    this.setText("[data-live='pv2-volts']", fmtNum(detailed("pv2_voltage"), 1));
    this.setText("[data-live='pv2-amps']", fmtNum(detailed("pv2_current"), 1));

    this.setText("[data-live='grid-main']", gridMainText);
    this.setText("[data-live='grid-l1-power']", formatKw(detailed("grid_l1_power")));
    this.setText("[data-live='grid-l1-volt']", fmtNum(detailed("grid_l1_voltage"), 1));
    this.setText("[data-live='grid-l2-power']", formatKw(detailed("grid_l2_power")));
    this.setText("[data-live='grid-l2-volt']", fmtNum(detailed("grid_l2_voltage"), 1));
    this.setText("[data-live='grid-l3-power']", formatKw(detailed("grid_l3_power")));
    this.setText("[data-live='grid-l3-volt']", fmtNum(detailed("grid_l3_voltage"), 1));
    this.setText("[data-live='grid-bought']", fmtNum(detailed("daily_energy_bought"), 2));
    this.setText("[data-live='grid-sold']", fmtNum(detailed("daily_energy_sold"), 2));
    this.setText("[data-live='grid-frequency']", fmtNum(detailed("load_frequency"), 2));

    this.setText("[data-live='battery-soc-value']", batterySocValue === null ? "—" : `${Math.round(batterySocValue)}`);
    this.setText("[data-live='battery-direction']", batteryDirectionText);
    this.setText("[data-live='battery-voltage']", fmtNum(detailed("battery_bms_voltage"), 1));
    this.setText("[data-live='battery-current']", fmtNum(detailed("battery_current"), 1));
    this.setText("[data-live='battery-temp']", fmtNum(detailed("battery_temperature"), 1));
    this.setText("[data-live='battery-charge-daily']", fmtNum(detailed("daily_battery_charge"), 2));
    this.setText("[data-live='battery-discharge-daily']", fmtNum(detailed("daily_battery_discharge"), 2));

    this.setText("[data-live='load-main']", formatKw(loadValue));
    this.setText("[data-live='load-daily']", fmtNum(detailed("daily_load_consumption"), 2));
    this.setText("[data-live='load-l1-power']", formatKw(detailed("load_l1_power")));
    this.setText("[data-live='load-l2-power']", formatKw(detailed("load_l2_power")));
    this.setText("[data-live='load-l3-power']", formatKw(detailed("load_l3_power")));

    this.setText("[data-live='inverter-temp']", detailed("inverter_ac_temperature") === null ? "—" : `${Math.round(detailed("inverter_ac_temperature"))}`);
    const soldKwh = this.asNumber(this.state(this.entity("sensor", "sold_energy_today")), null);
    const soldPln = this.asNumber(this.state(this.entity("sensor", "sold_value_today")), null);
    this.setText("[data-live='sold-today-line']", `${fmtNum(soldKwh, 2)} kWh / ${fmtNum(soldPln, 2)} PLN`);

    this.setText("[data-live='active-slot']", activeSlotLabel);
    this.setText("[data-live='manager-mode']", modeText);
    this.setText("[data-live='manager-active-mode']", modeText);
    this.setText("[data-live='decision-reason']", this.state(this.entity("sensor", "decision_reason"), "—"));
    this.setText("[data-live='deye-mode']", currentModeValue || "—");
    this.setText("[data-live='manager-deye-mode']", currentModeValue || "—");
    this.setClass("[data-live='manager-active-mode']", safeModeClass(managerModeClass), "", false);
    this.setClass("[data-live='manager-mode']", safeModeClass(managerModeClass), "", false);
    this.setClass("[data-live='deye-mode']", safeModeClass(currentModeMeta.cls), "", false);

    this.updateFlowLines();
    this.scaleFlowPanel();

    this.querySelector("[data-action='sell']")?.classList.toggle("active", sellActive);
    this.querySelector("[data-action='stop']")?.classList.toggle("active", stopActive);
    this.querySelector("[data-action='defaults']")?.classList.toggle("active", defaultButtonActive);

    this.setText("[data-live='target-mode']", this.state(this.entity("sensor", "target_mode")));
    this.setText("[data-live='target-sell-power']", `${this.state(this.entity("sensor", "target_sell_power"))} W`);
    this.setText("[data-live='target-discharge']", `${this.state(this.entity("sensor", "target_discharge_current"))} A`);
    this.setText("[data-live='target-charge']", `${this.state(this.entity("sensor", "target_charge_current"))} A`);
    this.setText("[data-live='current-mode']", this.state(this.entity("sensor", "current_work_mode")));
    this.setText("[data-live='current-sell-power']", `${this.state(this.entity("sensor", "current_sell_power"))} W`);
    this.setText("[data-live='current-discharge']", `${this.state(this.entity("sensor", "current_discharge_current"))} A`);
    this.setText("[data-live='current-charge']", `${this.state(this.entity("sensor", "current_charge_current"))} A`);
    this.setText("[data-live='current-grid-charge']", `${this.state(this.entity("sensor", "current_grid_charge_current"))} A`);

    const slowEntities = [sellPriceToday, sellPriceTomorrow, buyPriceToday, buyPriceTomorrow, this.entity("sensor", "ai_state"),
      solcastToday, solcastTomorrow, solcastDay3, solcastDay4, solcastDay5, solcastDay6,
      solcastDay7, solcastRemaining, solcastPeakPower, dailyPvProduction, solcastAccuracy,
      soldEnergyToday, soldValueToday];
    const slowSignature = slowEntities.map((entityId) => {
      const entity = this._hass?.states?.[entityId];
      return `${entityId}:${entity?.state}:${entity?.last_updated || ""}`;
    }).join("|");
    if (slowSignature === this._lastSlowSignature) {
      this.updateToggleButtons();
      return;
    }
    this._lastSlowSignature = slowSignature;

    const currentHour = this.localDateTimeParts()?.hour ?? new Date().getHours();
    const canonicalSellNow = this.canonicalPriceMaps("sell")[0].get(currentHour);
    this.setText("[data-live='sell-now']", `${this.formatPrice(canonicalSellNow)} PLN/kWh`);
    this.updatePriceTable("sell-prices", sellPriceToday, sellPriceTomorrow, priceThreshold, true);

    this.setText("[data-live='target-mode']", this.state(this.entity("sensor", "target_mode")));
    this.setText("[data-live='target-sell-power']", `${this.state(this.entity("sensor", "target_sell_power"))} W`);
    this.setText("[data-live='target-discharge']", `${this.state(this.entity("sensor", "target_discharge_current"))} A`);
    this.setText("[data-live='target-charge']", `${this.state(this.entity("sensor", "target_charge_current"))} A`);
    this.setText("[data-live='current-mode']", this.state(this.entity("sensor", "current_work_mode")));
    this.setText("[data-live='current-sell-power']", `${this.state(this.entity("sensor", "current_sell_power"))} W`);
    this.setText("[data-live='current-discharge']", `${this.state(this.entity("sensor", "current_discharge_current"))} A`);
    this.setText("[data-live='current-charge']", `${this.state(this.entity("sensor", "current_charge_current"))} A`);
    this.setText("[data-live='current-grid-charge']", `${this.state(this.entity("sensor", "current_grid_charge_current"))} A`);

    const canonicalBuyNow = this.canonicalPriceMaps("buy")[0].get(currentHour);
    this.setText("[data-live='buy-now']", `${this.formatPrice(canonicalBuyNow)} PLN/kWh`);
    this.updatePriceTable("buy-prices", buyPriceToday, buyPriceTomorrow, 0, false);
    this.setText("[data-live='solcast-power']", this.formatPower(this.state(solcastPower)));
    const solcastAccuracyAttrs = this._hass?.states?.[solcastAccuracy]?.attributes || {};
    const solcastForecastValue = this.asNumber(solcastAccuracyAttrs.forecast_today_kwh);
    const dailyPvValue = this.asNumber(solcastAccuracyAttrs.production_today_kwh);
    const solcastDifference = this.asNumber(solcastAccuracyAttrs.forecast_difference_today_kwh);
    const realizationTodayValue = this.asNumber(solcastAccuracyAttrs.realization_today_pct);
    const historicalAccuracyValue = this.asNumber(solcastAccuracyAttrs.historical_accuracy_pct)
      ?? this.asNumber(this.state(solcastAccuracy));
    const remainingForecastValue = this.asNumber(solcastAccuracyAttrs.remaining_forecast_kwh);
    const forecastTomorrowValue = this.asNumber(solcastAccuracyAttrs.forecast_tomorrow_kwh);
    this.setText("[data-live='solcast-today']", this.formatEnergy(solcastForecastValue));
    this.setText("[data-live='solcast-remaining']", this.formatEnergy(remainingForecastValue));
    this.setText("[data-live='solcast-tomorrow']", this.formatEnergy(forecastTomorrowValue));
    this.setText("[data-live='solcast-peak-power']", this.formatPower(this.state(solcastPeakPower)));
    this.setText("[data-live='solcast-best-day']", this.bestSolcastDay([solcastToday, solcastTomorrow, solcastDay3, solcastDay4, solcastDay5, solcastDay6, solcastDay7]));
    this.setText("[data-live='solcast-performance-forecast']", this.formatEnergy(solcastForecastValue));
    this.setText("[data-live='solcast-performance-actual']", this.formatEnergy(dailyPvValue));
    this.setText("[data-live='solcast-performance-difference']", this.formatSignedEnergy(solcastDifference));
    this.setText("[data-live='solcast-performance-progress']", realizationTodayValue === null ? "brak" : `${realizationTodayValue.toFixed(1)} %`);
    this.setText("[data-live='solcast-performance-accuracy']", historicalAccuracyValue === null ? "brak" : `${historicalAccuracyValue.toFixed(1)} %`);
    if (!this.isInteracting()) {
      this.setHtml("[data-live-html='solcast-days']", this.solcastDaysChart([solcastToday, solcastTomorrow, solcastDay3, solcastDay4, solcastDay5, solcastDay6, solcastDay7]));
      this.setHtml("[data-live-html='solcast-chart']", this.solcastChart(solcastToday, solcastTomorrow));
    }
    if (!this.isInteracting()) {
      const salesScrollTop = this.querySelector("[data-scroll-key='sales-month']")?.scrollTop;
      const salesHourlyTop = this.querySelector("[data-scroll-key='sales-hourly']")?.scrollTop;
      this.setHtml("[data-live-html='sales-stats']", this.salesStatsPanel());
      const salesScroll = this.querySelector("[data-scroll-key='sales-month']");
      const salesHourly = this.querySelector("[data-scroll-key='sales-hourly']");
      if (salesScrollTop !== undefined && salesScroll) salesScroll.scrollTop = salesScrollTop;
      if (salesHourlyTop !== undefined && salesHourly) salesHourly.scrollTop = salesHourlyTop;
      if (salesScroll) this.attachScrollHandlers(salesScroll);
      if (salesHourly) this.attachScrollHandlers(salesHourly);
    }
    this.updateToggleButtons();
    this.syncNormalProfileControls();
  }

  updatePriceTable(scrollKey, todayEntity, tomorrowEntity, threshold = 0, highIsGood = true) {
    const [today, tomorrow] = this.canonicalPriceMaps(scrollKey.startsWith("buy") ? "buy" : "sell");
    const currentHour = new Date().getHours();
    for (let hour = 0; hour < 24; hour += 1) {
      this.setHtml(`[data-price='${scrollKey}:today:${hour}']`, this.priceCell(today.get(hour), threshold, highIsGood));
      this.setHtml(`[data-price='${scrollKey}:tomorrow:${hour}']`, this.priceCell(tomorrow.get(hour), threshold, highIsGood));
      this.querySelector(`[data-price-row='${scrollKey}:${hour}']`)?.classList.toggle("active", hour === currentHour);
    }
  }

  exists(entityId) {
    return Boolean(this._hass?.states?.[entityId]);
  }

  state(entityId, fallback = "brak") {
    return this._hass?.states?.[entityId]?.state ?? fallback;
  }

  displayState(entityId, fallback = "brak") {
    if (Object.prototype.hasOwnProperty.call(this._optimisticStates || {}, entityId)) {
      const actual = this.state(entityId, fallback);
      const optimistic = this._optimisticStates[entityId];
      const actualNumber = this.asNumber(actual);
      const optimisticNumber = this.asNumber(optimistic);
      const numericComparable = /\d/.test(String(actual)) && /\d/.test(String(optimistic));
      const valuesMatch = actual === optimistic
        || (numericComparable && actualNumber !== null && optimisticNumber !== null && actualNumber === optimisticNumber);
      if (valuesMatch) {
        delete this._optimisticStates[entityId];
      } else {
        return optimistic;
      }
    }
    return this.state(entityId, fallback);
  }

  numberState(entityId, fallback = "0") {
    const value = this.displayState(entityId, fallback);
    return value === "unknown" || value === "unavailable" ? fallback : value;
  }

  asNumber(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === "number") return Number.isFinite(value) ? value : null;
    const text = String(value).trim();
    if (!text || ["unknown", "unavailable", "none", "null", "nan", "inf", "-inf"].includes(text.toLowerCase())) return null;
    const normalized = text.replace(",", ".");
    const match = normalized.match(/[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?/i);
    if (!match) return null;
    const remainder = `${normalized.slice(0, match.index)}${normalized.slice((match.index || 0) + match[0].length)}`;
    if (/\d/.test(remainder)) return null;
    const parsed = Number(match[0]);
    return Number.isFinite(parsed) ? parsed : null;
  }

  optionalSocNumber(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === "number") {
      return Number.isFinite(value) && value >= 0 && value <= 100 ? value : null;
    }
    const text = String(value).trim();
    if (!text || ["unknown", "unavailable", "none", "null", "nan"].includes(text.toLowerCase())) {
      return null;
    }
    if (!/^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(text)) return null;
    const parsed = Number(text.replace(",", "."));
    return Number.isFinite(parsed) && parsed >= 0 && parsed <= 100 ? parsed : null;
  }

  formatPrice(value) {
    const number = this.asNumber(value);
    if (number === null) return "brak";
    return number.toFixed(2);
  }

  formatNumber(value, digits = 2) {
    const number = this.asNumber(value);
    return number === null ? "brak" : number.toFixed(digits);
  }

  formatSignedMoney(value) {
    const number = this.asNumber(value);
    if (number === null) return "brak danych";
    return `${number >= 0 ? "+" : ""}${number.toFixed(2).replace(".", ",")} zł`;
  }

  hourLabel(hour) {
    const start = String(hour).padStart(2, "0");
    const end = String((hour + 1) % 24).padStart(2, "0");
    return `${start}-${end}`;
  }

  localDateTimeParts(value = new Date()) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    const timeZone = this._hass?.config?.time_zone || undefined;
    try {
      const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        hourCycle: "h23",
      }).formatToParts(date).reduce((result, item) => {
        if (item.type !== "literal") result[item.type] = item.value;
        return result;
      }, {});
      const hour = Number(parts.hour);
      return {
        date: `${parts.year}-${parts.month}-${parts.day}`,
        hour: hour === 24 ? 0 : hour,
      };
    } catch (_error) {
      return null;
    }
  }

  priceSlotFromValue(value, fallback = null) {
    if (typeof value === "number" && value >= 0 && value < 24) {
      return { date: null, hour: Math.floor(value) };
    }
    const text = String(value ?? "").trim();
    const isoMatch = text.match(
      /^(\d{4})-(\d{2})-(\d{2})[T ](\d{1,2}):\d{2}(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$/i
    );
    if (isoMatch) {
      if (isoMatch[5]) {
        const localized = this.localDateTimeParts(text.replace(" ", "T"));
        if (localized) return localized;
      }
      const hour = Number(isoMatch[4]);
      if (hour >= 0 && hour < 24) {
        return { date: `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`, hour };
      }
    }
    const hourMatch = text.match(/(^|\D)(\d{1,2})(?::\d{2})?/);
    if (hourMatch) {
      const hour = Number(hourMatch[2]);
      if (hour >= 0 && hour < 24) return { date: null, hour };
    }
    return { date: null, hour: fallback };
  }

  hourFromValue(value, fallback = null) {
    return this.priceSlotFromValue(value, fallback).hour;
  }

  priceFromObject(item) {
    if (!item || typeof item !== "object") return null;
    const keys = [
      "price", "value", "state", "amount", "total", "net_price", "gross_price",
      "energy_price", "unit_price", "price_with_tax", "pln_kwh", "pln_per_kwh",
      "sell_price", "buy_price", "sprzedaz", "zakup", "cena", "pln", "rce"
    ];
    for (const key of keys) {
      if (item[key] !== undefined) {
        const value = this.asNumber(item[key]);
        if (value !== null) return value;
      }
    }
    return null;
  }

  timeFromObject(item) {
    if (!item || typeof item !== "object") return null;
    const keys = [
      "hour", "start", "from", "time", "date", "datetime", "timestamp", "period", "label", "name",
      "start_time", "starts_at", "valid_from", "valid_from_date", "begin", "od"
    ];
    for (const key of keys) {
      if (item[key] !== undefined) return item[key];
    }
    return null;
  }

  addPriceCandidate(candidates, item, fallbackHour = null) {
    let slot = { date: null, hour: null };
    let hour = null;
    let price = null;
    if (Array.isArray(item)) {
      slot = this.priceSlotFromValue(item[0], fallbackHour);
      hour = slot.hour;
      price = this.asNumber(item[1]);
    } else if (item && typeof item === "object") {
      slot = this.priceSlotFromValue(this.timeFromObject(item), fallbackHour);
      hour = slot.hour;
      price = this.priceFromObject(item);
    } else {
      hour = fallbackHour;
      price = this.asNumber(item);
    }
    if (hour !== null && price !== null) candidates.push({ date: slot.date, hour, price });
  }

  readPriceCandidates(entityId, allowStateFallback = true) {
    const entity = this._hass?.states?.[entityId];
    const candidates = [];
    if (!entity) return candidates;

    const parseSource = (source) => {
      if (source === null || source === undefined) return;
      if (Array.isArray(source)) {
        source.forEach((item, index) => this.addPriceCandidate(candidates, item, index < 24 ? index : null));
        return;
      }
      if (typeof source === "object") {
        Object.entries(source).forEach(([key, value], index) => {
          if (value && typeof value === "object" && !Array.isArray(value)) {
            this.addPriceCandidate(candidates, { ...value, hour: value.hour ?? key }, index < 24 ? index : null);
          } else {
            this.addPriceCandidate(candidates, [key, value], index < 24 ? index : null);
          }
        });
      }
    };

    const attrs = entity.attributes || {};
    [
      attrs.prices, attrs.price, attrs.today, attrs.tomorrow, attrs.hourly, attrs.hours,
      attrs.data, attrs.values, attrs.items, attrs.entries, attrs.forecast,
      attrs.raw_today, attrs.raw_tomorrow, attrs.source, attrs.price_list, attrs.hourly_prices,
      attrs.prices_today, attrs.prices_tomorrow, attrs.today_prices, attrs.tomorrow_prices,
      attrs.sell_prices, attrs.buy_prices, attrs.ceny, attrs.ceny_godzinowe, attrs.energy_prices
    ].forEach(parseSource);

    if (candidates.length === 0 && allowStateFallback) {
      Object.entries(attrs).forEach(([key, value], index) => {
        if (this.hourFromValue(key) !== null || Array.isArray(value) || (value && typeof value === "object")) {
          parseSource({ [key]: value });
        }
      });
    }

    if (candidates.length === 0) {
      const currentHour = this.localDateTimeParts()?.hour ?? new Date().getHours();
      const stateValue = this.asNumber(entity.state);
      if (stateValue !== null) candidates.push({ date: null, hour: currentHour, price: stateValue });
    }
    return candidates;
  }

  readPriceMap(entityId, allowStateFallback = true) {
    const map = new Map();
    this.readPriceCandidates(entityId, allowStateFallback).forEach(({ hour, price }) => {
      if (!map.has(hour)) map.set(hour, price);
    });
    return map;
  }

  readPriceMaps(todayEntityId, tomorrowEntityId, reference = new Date()) {
    const maps = [new Map(), new Map()];
    const today = this.localDateTimeParts(reference)?.date;
    const dayOffset = (localDate) => {
      if (!today || !localDate) return null;
      const parse = (text) => {
        const [year, month, day] = text.split("-").map(Number);
        return Date.UTC(year, month - 1, day);
      };
      return Math.round((parse(localDate) - parse(today)) / 86400000);
    };
    [
      [todayEntityId, true],
      [tomorrowEntityId, false],
    ].forEach(([entityId, allowFallback], sourceDay) => {
      this.readPriceCandidates(entityId, allowFallback).forEach(({ date, hour, price }) => {
        const bucket = date === null ? sourceDay : dayOffset(date);
        if ((bucket === 0 || bucket === 1) && !maps[bucket].has(hour)) {
          maps[bucket].set(hour, price);
        }
      });
    });
    return maps;
  }

  priceCell(value, threshold = 0, highIsGood = true) {
    const number = this.asNumber(value);
    if (number === null) return `<span class="price missing">brak</span>`;
    let cls = "";
    if (threshold > 0) cls = highIsGood ? (number >= threshold ? "good" : "warn") : (number <= threshold ? "good" : "warn");
    return `<span class="price ${cls}">${this.formatPrice(number)}</span>`;
  }

  priceTable(todayEntity, tomorrowEntity, threshold = 0, highIsGood = true, scrollKey = "prices") {
    const [today, tomorrow] = this.canonicalPriceMaps(scrollKey.startsWith("buy") ? "buy" : "sell");
    const currentHour = this.localDateTimeParts()?.hour ?? new Date().getHours();
    return `<div class="price-scroll" data-scroll-key="${scrollKey}"><table class="price-table">
      <thead><tr><th>Godz.</th><th>Dzisiaj</th><th>Jutro</th></tr></thead>
      <tbody>${Array.from({ length: 24 }, (_, hour) => `<tr class="${hour === currentHour ? "active" : ""}" data-price-row="${scrollKey}:${hour}">
        <td>${this.hourLabel(hour)}</td>
        <td data-price="${scrollKey}:today:${hour}">${this.priceCell(today.get(hour), threshold, highIsGood)}</td>
        <td data-price="${scrollKey}:tomorrow:${hour}">${this.priceCell(tomorrow.get(hour), threshold, highIsGood)}</td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  formatPower(value) {
    const number = this.asNumber(value);
    if (number === null) return "brak";
    if (Math.abs(number) >= 1000) return `${(number / 1000).toFixed(2)} kW`;
    return `${Math.round(number)} W`;
  }

  formatEnergy(value) {
    const number = this.asNumber(value);
    if (number === null) return "brak";
    return `${number.toFixed(2)} kWh`;
  }

  formatSignedEnergy(value) {
    const number = this.asNumber(value);
    if (number === null) return "brak";
    return `${number > 0 ? "+" : ""}${number.toFixed(2)} kWh`;
  }

  formatTimeShort(value) {
    const text = String(value ?? "");
    if (!text || text === "unknown" || text === "unavailable" || text === "brak") return "brak";
    const date = new Date(text);
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    const match = text.match(/(\d{1,2}):(\d{2})/);
    return match ? `${match[1].padStart(2, "0")}:${match[2]}` : text;
  }

  forecastFromObject(item) {
    if (!item || typeof item !== "object") return null;
    const keys = ["pv_estimate", "estimate", "value", "energy", "kwh", "forecast", "state"];
    for (const key of keys) {
      if (item[key] !== undefined) {
        const value = this.asNumber(item[key]);
        if (value !== null) return value;
      }
    }
    return null;
  }

  forecastTimeFromObject(item) {
    if (!item || typeof item !== "object") return null;
    const keys = ["period_start", "start", "from", "time", "datetime", "timestamp", "hour"];
    for (const key of keys) {
      if (item[key] !== undefined) return item[key];
    }
    return null;
  }

  addForecastCandidate(map, item, fallbackHour = null, aggregate = false) {
    let hour = null;
    let value = null;
    if (Array.isArray(item)) {
      hour = this.hourFromValue(item[0], fallbackHour);
      value = this.asNumber(item[1]);
    } else if (item && typeof item === "object") {
      hour = this.hourFromValue(this.forecastTimeFromObject(item), fallbackHour);
      value = this.forecastFromObject(item);
    } else {
      hour = fallbackHour;
      value = this.asNumber(item);
    }
    if (hour === null || value === null || value < 0) return;
    map.set(hour, aggregate ? (map.get(hour) || 0) + value : (map.has(hour) ? map.get(hour) : value));
  }

  readForecastMap(entityId) {
    const entity = this._hass?.states?.[entityId];
    const map = new Map();
    if (!entity) return map;
    const attrs = entity.attributes || {};

    const parseSource = (source, aggregate = false) => {
      if (!source) return;
      if (Array.isArray(source)) {
        source.forEach((item, index) => this.addForecastCandidate(map, item, index < 24 ? index : null, aggregate));
        return;
      }
      if (typeof source === "object") {
        Object.entries(source).forEach(([key, value], index) => {
          const fallbackHour = index < 24 ? index : null;
          if (value && typeof value === "object" && !Array.isArray(value)) {
            this.addForecastCandidate(map, { ...value, hour: value.hour ?? key }, fallbackHour, aggregate);
          } else {
            this.addForecastCandidate(map, [key, value], fallbackHour, aggregate);
          }
        });
      }
    };

    [
      attrs.detailedHourly,
      attrs.detailed_hourly,
      attrs.hourly,
      attrs.hours,
      attrs.today,
      attrs.tomorrow,
    ].forEach((source) => parseSource(source, false));

    if (map.size === 0) {
      [attrs.detailedForecast, attrs.detailed_forecast, attrs.forecast, attrs.intervals].forEach((source) => parseSource(source, true));
    }
    return map;
  }

  solcastChart(todayEntity, tomorrowEntity) {
    const today = this.readForecastMap(todayEntity);
    const tomorrow = this.readForecastMap(tomorrowEntity);
    const values = [...today.values(), ...tomorrow.values()].map((value) => this.asNumber(value) || 0);
    const max = Math.max(0.001, ...values);
    const currentHour = new Date().getHours();
    const bars = Array.from({ length: 24 }, (_, hour) => {
      const todayValue = this.asNumber(today.get(hour)) || 0;
      const tomorrowValue = this.asNumber(tomorrow.get(hour)) || 0;
      const todayHeight = Math.max(3, Math.round((todayValue / max) * 100));
      const tomorrowHeight = Math.max(3, Math.round((tomorrowValue / max) * 100));
      return `<div class="solcast-bar ${hour === currentHour ? "now" : ""}" title="${this.hourLabel(hour)}: dzisiaj ${todayValue.toFixed(2)} kWh, jutro ${tomorrowValue.toFixed(2)} kWh">
        <div class="solcast-columns">
          <span class="today" style="height:${todayHeight}%"></span>
          <span class="tomorrow" style="height:${tomorrowHeight}%"></span>
        </div>
        <em>${String(hour).padStart(2, "0")}</em>
      </div>`;
    }).join("");
    return `<div class="solcast-chart"><div class="solcast-bars">${bars}</div></div>
      <div class="solcast-legend"><span class="today"></span>Dzisiaj <span class="tomorrow"></span>Jutro</div>`;
  }

  solcastDaysChart(entities) {
    const days = this.solcastDayData(entities);
    const max = Math.max(0.001, ...days.map((day) => day.value || 0));
    const bars = days.map((day) => {
      const number = day.value || 0;
      const height = Math.max(6, Math.round((number / max) * 100));
      const missing = day.value === null;
      return `<div class="solcast-day ${missing ? "missing" : ""}" title="${day.label}: ${missing ? "brak" : `${number.toFixed(2)} kWh`}">
        <div class="solcast-day-head"><strong>${day.label}</strong><em>${day.date}</em></div>
        <div class="solcast-day-meter"><span style="height:${height}%"></span></div>
        <b>${missing ? "-" : number.toFixed(1)} kWh</b>
      </div>`;
    }).join("");
    return `<div class="solcast-days">${bars}</div>`;
  }

  solcastDayData(entities) {
    const labels = ["Dzi\u015b", "Jutro", "za 2 dni", "za 3 dni", "za 4 dni", "za 5 dni", "za 6 dni"];
    return entities.map((entityId, index) => {
      const date = new Date();
      date.setHours(12, 0, 0, 0);
      date.setDate(date.getDate() + index);
      return {
        label: labels[index],
        date: date.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit" }),
        value: this.asNumber(this.state(entityId)),
      };
    });
  }

  bestSolcastDay(entities) {
    const days = this.solcastDayData(entities).filter((day) => day.value !== null);
    if (!days.length) return "brak";
    const best = days.reduce((winner, day) => (day.value > winner.value ? day : winner), days[0]);
    return `${best.label} / ${best.value.toFixed(1)} kWh`;
  }

  salesAttributes() {
    return this._hass?.states?.[this.entity("sensor", "sold_energy_today")]?.attributes || {};
  }

  salesRows(key) {
    const attrs = this.salesAttributes();
    const rows = attrs[key];
    return Array.isArray(rows) ? rows : [];
  }

  formatKwh(value) {
    const number = this.asNumber(value);
    if (number === null) return "0.000";
    return number.toFixed(3);
  }

  formatMoney(value) {
    const number = this.asNumber(value);
    if (number === null) return "0.00";
    return number.toFixed(2);
  }

  salesStatsPanel() {
    const attrs = this.salesAttributes();
    const hourly = this.salesRows("hourly_today");
    const week = this.salesRows("week");
    const month = this.salesRows("month");
    const todayKwh = this.asNumber(this.state(this.entity("sensor", "sold_energy_today"), 0)) || 0;
    const todayValue = this.asNumber(attrs.sold_value_today) || this.asNumber(this.state(this.entity("sensor", "sold_value_today"), 0)) || 0;
    const hourKwh = this.asNumber(attrs.sold_energy_current_hour) || this.asNumber(this.state(this.entity("sensor", "sold_energy_current_hour"), 0)) || 0;
    const hourValue = this.asNumber(attrs.sold_value_current_hour) || this.asNumber(this.state(this.entity("sensor", "sold_value_current_hour"), 0)) || 0;
    const maxHour = Math.max(0.001, ...hourly.map((row) => this.asNumber(row.kwh) || 0));
    const weekKwh = this.asNumber(attrs.sold_energy_week) || week.reduce((sum, row) => sum + (this.asNumber(row.kwh) || 0), 0);
    const weekValue = this.asNumber(attrs.sold_value_week) || week.reduce((sum, row) => sum + (this.asNumber(row.value) || 0), 0);
    const monthKwh = this.asNumber(attrs.sold_energy_month) || month.reduce((sum, row) => sum + (this.asNumber(row.kwh) || 0), 0);
    const monthValue = this.asNumber(attrs.sold_value_month) || month.reduce((sum, row) => sum + (this.asNumber(row.value) || 0), 0);
    const currentHour = new Date().getHours();

    const bars = hourly.map((row) => {
      const hour = this.asNumber(row.hour) ?? 0;
      const kwh = this.asNumber(row.kwh) || 0;
      const value = this.asNumber(row.value) || 0;
      const height = Math.max(4, Math.round((kwh / maxHour) * 86));
      return `<div class="sales-bar ${hour === currentHour ? "now" : ""}" title="${row.label}: ${this.formatKwh(kwh)} kWh / ${this.formatMoney(value)} PLN">
        <span style="height:${height}%"></span><em>${String(hour).padStart(2, "0")}</em>
      </div>`;
    }).join("");

    const dailyRows = (rows, emptyText) => {
      if (!rows.length) return `<tr><td colspan="3">${emptyText}</td></tr>`;
      return rows.slice(-31).reverse().map((row) => `<tr>
        <td>${row.label || row.date || "-"}</td>
        <td>${this.formatKwh(row.kwh)} kWh</td>
        <td>${this.formatMoney(row.value)} PLN</td>
      </tr>`).join("");
    };
    const hourlyRows = hourly.map((row) => `<tr>
      <td>${row.label || this.hourLabel(row.hour || 0)}</td>
      <td>${this.formatKwh(row.kwh)} kWh</td>
      <td>${this.formatMoney(row.value)} PLN</td>
    </tr>`).join("");

    return `
      <div class="sales-summary">
        ${this.stat("Dzisiaj energia", `${this.formatKwh(todayKwh)} kWh`, "sales-energy", "", "sell")}
        ${this.stat("Dzisiaj warto\u015b\u0107", `${this.formatMoney(todayValue)} PLN`, "sales-value", "", "money")}
        ${this.stat("Ta godzina", `${this.formatKwh(hourKwh)} kWh / ${this.formatMoney(hourValue)} PLN`, "sales-hour", "", "clock")}
        ${this.stat("Tydzie\u0144", `${this.formatKwh(weekKwh)} kWh / ${this.formatMoney(weekValue)} PLN`, "sales-week", "", "chart")}
        ${this.stat("Miesi\u0105c", `${this.formatKwh(monthKwh)} kWh / ${this.formatMoney(monthValue)} PLN`, "sales-month", "", "calendar")}
      </div>
      <div class="sales-chart">${bars}</div>
      <div class="sales-tables">
        <div><div class="section-label">Dzisiaj godzina po godzinie</div><div class="sales-scroll" data-scroll-key="sales-hourly"><table class="mini-table"><tbody>${hourlyRows}</tbody></table></div></div>
        <div><div class="section-label">Ostatnie 7 dni</div><table class="mini-table"><tbody>${dailyRows(week, "Brak historii tygodnia")}</tbody></table></div>
        <div><div class="section-label">Bie\u017c\u0105cy miesi\u0105c</div><div class="sales-scroll" data-scroll-key="sales-month"><table class="mini-table"><tbody>${dailyRows(month, "Brak historii miesi\u0105ca")}</tbody></table></div></div>
      </div>`;
  }

  options(entityId, fallback = []) {
    return this._hass?.states?.[entityId]?.attributes?.options || fallback;
  }

  norm(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  exactEntity(domain, suffixes) {
    const list = Array.isArray(suffixes) ? suffixes : [suffixes];
    for (const suffix of list) {
      const direct = `${domain}.deye_energy_manager_${suffix}`;
      if (this.exists(direct)) return direct;
      const doubled = `${domain}.deye_energy_manager_deye_energy_manager_${suffix}`;
      if (this.exists(doubled)) return doubled;
    }
    return "";
  }

  entity(domain, suffixes) {
    const list = Array.isArray(suffixes) ? suffixes : [suffixes];
    const exact = this.exactEntity(domain, list);
    if (exact) return exact;

    const candidates = Object.keys(this._hass.states).filter((id) => id.startsWith(`${domain}.`));
    for (const suffix of list) {
      const normalized = this.norm(suffix);
      const found = candidates.find((id) => {
        const flatId = this.norm(id);
        const friendly = this.norm(this._hass.states[id]?.attributes?.friendly_name || "");
        return (flatId.includes("deyeenergymanager") && flatId.includes(normalized))
          || (friendly.includes("deyeenergymanager") && friendly.includes(normalized));
      });
      if (found) return found;
    }
    return `${domain}.deye_energy_manager_${list[0]}`;
  }

  deyeWorkModeEntity() {
    const configured = [
      this.config?.entities?.system_work_mode,
      this.config?.entities?.deye_system_work_mode,
      this.config?.entity_map?.system_work_mode,
      this.config?.mapping?.system_work_mode,
      this.config?.system_work_mode,
      this.config?.deye_work_mode_entity,
    ].filter((entityId) => typeof entityId === "string" && entityId.trim());
    const candidates = [...configured, "select.deye_inverter_system_work_mode"];
    return candidates.find((entityId) => this.exists(entityId)) || "select.deye_inverter_system_work_mode";
  }

  deyeWorkModeState() {
    const value = String(this.state(this.deyeWorkModeEntity(), "") || "").trim();
    return ["unknown", "unavailable", "none", "null", "enabled", "disabled"].includes(value.toLowerCase()) ? "" : value;
  }

  findEntity(domain, wanted, excluded = [], fallbackSuffixes = []) {
    const fallbackList = Array.isArray(fallbackSuffixes) ? fallbackSuffixes : [fallbackSuffixes];
    const byId = this.exactEntity(domain, fallbackList);
    if (byId) return byId;
    const wantedParts = wanted.map((value) => this.norm(value)).filter(Boolean);
    const excludedParts = excluded.map((value) => this.norm(value)).filter(Boolean);
    const found = Object.entries(this._hass.states).find(([id, entity]) => {
      if (!id.startsWith(`${domain}.`)) return false;
      const friendly = this.norm(entity.attributes?.friendly_name || "");
      const flatId = this.norm(id);
      const haystack = `${flatId} ${friendly}`;
      return wantedParts.every((part) => haystack.includes(part))
        && !excludedParts.some((part) => haystack.includes(part));
    });
    return found?.[0] || `${domain}.deye_energy_manager_${fallbackList[0] || wantedParts.join("_")}`;
  }

  slotEntity(domain, key, label, suffixes, wanted, excluded = []) {
    const fallbackList = Array.isArray(suffixes) ? suffixes : [suffixes];
    const byId = this.exactEntity(domain, fallbackList);
    if (byId) return byId;

    const candidates = Object.entries(this._hass.states).filter(([id]) => id.startsWith(`${domain}.`));
    const excludedParts = excluded.map((value) => this.norm(value)).filter(Boolean);
    const keyToken = this.norm(`slot_${key}`);
    const labelToken = this.norm(label);
    const wantedParts = wanted.map((value) => this.norm(value)).filter(Boolean);

    const matches = ([id, entity], requireKeyToken = true) => {
      const flatId = this.norm(id);
      const friendly = this.norm(entity.attributes?.friendly_name || "");
      const haystack = `${flatId} ${friendly}`;
      const hasSlot = requireKeyToken
        ? flatId.includes(keyToken)
        : flatId.includes(keyToken) || friendly.includes(labelToken);
      return hasSlot
        && wantedParts.every((part) => haystack.includes(part))
        && !excludedParts.some((part) => haystack.includes(part));
    };

    return candidates.find((entry) => matches(entry, true))?.[0]
      || candidates.find((entry) => matches(entry, false))?.[0]
      || this.findEntity(domain, [keyToken, ...wantedParts], excluded, fallbackList);
  }

  slotEntities(key, label) {
    return {
      sellEnabled: this.slotEntity("switch", key, label, [`slot_${key}_enabled`, `${key}_enabled`, `slot_${key}`, key], [], ["charge"]),
      mode: this.slotEntity("select", key, label, [`slot_${key}_mode`, `${key}_mode`], ["mode"]),
      sellPower: this.slotEntity("number", key, label, [`slot_${key}_sell_power`, `${key}_sell_power`], ["sell", "power"]),
      dischargeCurrent: this.slotEntity("number", key, label, [`slot_${key}_discharge_current`, `${key}_discharge_current`], ["discharge", "current"]),
      chargeCurrent: this.slotEntity("number", key, label, [`slot_${key}_charge_current`, `${key}_charge_current`], ["charge", "current"], ["discharge"]),
      gridChargeCurrent: this.slotEntity("number", key, label, [`slot_${key}_grid_charge_current`, `${key}_grid_charge_current`], ["grid", "charge", "current"]),
      chargeEnabled: this.slotEntity("switch", key, label, [`slot_${key}_charge_enabled`, `${key}_charge_enabled`], ["charge"], ["slot", "enabled"]),
      minimumSellSoc: this.slotEntity("number", key, label, [`slot_${key}_minimum_sell_soc`, `${key}_minimum_sell_soc`], ["minimum", "sell", "soc"]),
      touSoc: this.slotEntity("number", key, label, [`slot_${key}_tou_soc`, `${key}_tou_soc`], ["tou", "battery", "soc"]),
      minSellPrice: this.slotEntity("number", key, label, [`slot_${key}_min_sell_price`, `${key}_min_sell_price`], ["minimum", "sell", "price"]),
    };
  }

  scheduleEntityIds(slots = this.scheduleSlots()) {
    const ids = [];
    slots.forEach(([key, label]) => {
      Object.values(this.slotEntities(key, label)).forEach((entityId) => {
        if (entityId && !ids.includes(entityId)) ids.push(entityId);
      });
    });
    return ids;
  }

  scheduleStateSignature() {
    const ids = this._scheduleEntityIds?.length ? this._scheduleEntityIds : this.scheduleEntityIds();
    return ids.map((entityId) => `${entityId}:${this._hass?.states?.[entityId]?.state ?? ""}`).join("|");
  }

  chargeProfileStoredValues() {
    const statusId = this.entity("sensor", "manager_status");
    const profile = this._hass?.states?.[statusId]?.attributes?.charge_profile;
    return profile && typeof profile === "object" ? profile : {};
  }



  normalProfileStoredValues() {
    const statusId = this.entity("sensor", "manager_status");
    const profile = this._hass?.states?.[statusId]?.attributes?.normal_profile;
    return profile && typeof profile === "object" ? profile : {};
  }

  managerStatusAttributes() {
    return this._hass?.states?.[this.entity("sensor", "manager_status")]?.attributes || {};
  }

  controlContract() {
    const attributes = this.managerStatusAttributes();
    const control = attributes?.control;
    if (control && typeof control === "object") return control;
    return {
      entity_id: null,
      enabled: attributes.control_enabled === true,
      status: attributes.control_status,
    };
  }

  controlEntityId() {
    return this.controlState().entity_id;
  }

  controlEnabled() {
    return this.controlState().enabled;
  }

  controlStatus() {
    return this.controlState().status;
  }

  controlState() {
    const contract = this.controlContract();
    const entityId = typeof contract.entity_id === "string" && contract.entity_id.startsWith("switch.")
      ? contract.entity_id
      : "";
    const enabled = contract.enabled === true;
    const rawStatus = String(contract.status || "");
    let status = ["Aktywne", "Wyłączanie", "Wyłączone"].includes(rawStatus)
      ? rawStatus
      : (enabled ? "Aktywne" : "Wyłączone");
    const awaitingExpectedState = typeof this._controlExpectedEnabled === "boolean"
      && enabled !== this._controlExpectedEnabled;
    if (awaitingExpectedState && this._controlExpectedEnabled === false) status = "Wyłączanie";
    return {
      entity_id: entityId,
      enabled,
      status,
      pending: this._controlTogglePending || status === "Wyłączanie" || awaitingExpectedState,
    };
  }

  defaultSettingsStoredValues() {
    const values = this.managerStatusAttributes()?.default_settings;
    return values && typeof values === "object" ? values : {};
  }

  normalProfileModeOptions() {
    const rows = this.managerStatusAttributes()?.normal_profile_options;
    if (!Array.isArray(rows)) return [];
    return rows
      .filter((row) => row && row.available === true && row.value && row.label)
      .map((row) => [String(row.value), String(row.label)]);
  }

  canonicalNormalProfileMode(value) {
    const raw = value === null || value === undefined ? "" : String(value);
    const match = this.normalProfileModeOptions().find(([key, label]) => key === raw || label === raw);
    return match ? match[0] : "";
  }

  defaultWorkModes() {
    return ["Normalna Praca", "Sprzedaż"];
  }

  defaultSettingsMode() {
    const draft = this._defaultSettingsDraft.mode;
    if (draft && this.defaultWorkModes().includes(draft)) return draft;
    const stored = this.defaultSettingsStoredValues().mode;
    if (stored && this.defaultWorkModes().includes(stored)) return stored;
    const state = this.normalizeManagerMode(this.state(this.entity("select", "default_work_mode")));
    return this.defaultWorkModes().includes(state) ? state : "Normalna Praca";
  }

  defaultPhysicalWorkMode() {
    const draft = this._defaultSettingsDraft.physical_work_mode;
    if (draft) return this.canonicalNormalProfileMode(draft);
    const stored = this.defaultSettingsStoredValues().physical_work_mode;
    if (stored) return this.canonicalNormalProfileMode(stored);
    return this.canonicalNormalProfileMode(this.normalProfileStoredValues().physical_work_mode);
  }

  scheduleSlotSnapshot(key, label = "") {
    const canonical = this.managerStatusAttributes()?.schedule_slots?.[key];
    if (canonical && typeof canonical === "object") {
      return { slot_key: key, ...canonical, mode: this.normalizeManagerMode(canonical.mode) };
    }
    const entities = this.slotEntities(key, label);
    const mode = this.normalizeManagerMode(this.displayState(entities.mode, "Normalna Praca"));
    const physicalMode = mode === "Normalna Praca"
      ? (this.normalProfileStoredValues().physical_work_mode || null)
      : null;
    return {
      slot_key: key,
      enabled: this.displayState(entities.sellEnabled, "off") === "on",
      mode,
      physical_work_mode: physicalMode,
      sell_power: this.asNumber(this.numberState(entities.sellPower, 0)) ?? 0,
      discharge_current: this.asNumber(this.numberState(entities.dischargeCurrent, 0)) ?? 0,
      charge_enabled: this.displayState(entities.chargeEnabled, "off") === "on",
      charge_current: this.asNumber(this.numberState(entities.chargeCurrent, 0)) ?? 0,
      grid_charge_current: this.asNumber(this.numberState(entities.gridChargeCurrent, 0)) ?? 0,
      minimum_sell_soc: this.asNumber(this.numberState(entities.minimumSellSoc, 0)) ?? 0,
      tou_soc: this.asNumber(this.numberState(entities.touSoc, "")),
      min_sell_price: this.asNumber(this.numberState(entities.minSellPrice, 0)) ?? 0,
    };
  }

  slotEditFields() {
    return [
      "enabled", "mode", "physical_work_mode", "sell_power", "discharge_current",
      "charge_enabled", "charge_current", "grid_charge_current",
      "minimum_sell_soc", "tou_soc", "min_sell_price",
    ];
  }

  slotNumericFields() {
    return [
      "sell_power", "discharge_current", "charge_current", "grid_charge_current",
      "minimum_sell_soc", "tou_soc", "min_sell_price",
    ];
  }

  normalizeSlotEditValue(field, value) {
    if (field === "mode") return this.normalizeManagerMode(value);
    if (field === "enabled" || field === "charge_enabled") {
      if (typeof value === "string") return ["true", "on", "1", "tak", "yes"].includes(value.trim().toLowerCase());
      return Boolean(value);
    }
    if (this.slotNumericFields().includes(field)) {
      if (value === null || value === undefined || String(value).trim() === "") return null;
      const numeric = Number(String(value).replace(",", "."));
      return Number.isFinite(numeric) ? numeric : value;
    }
    return value === null || value === undefined ? null : String(value).trim();
  }

  normalizedSlotEdit(values) {
    return Object.fromEntries(this.slotEditFields().map((field) => [field, this.normalizeSlotEditValue(field, values?.[field])]));
  }

  isScheduleSlotDialog() {
    return this._dialog?.type === "sell" || this._dialog?.type === "slot";
  }

  openScheduleSlotEditor(key, label = "", type = "sell") {
    const snapshot = this.scheduleSlotSnapshot(key, label);
    this._slotEditOriginal = { key, label, values: { ...snapshot } };
    this._slotEditDraft = { key, label, values: { ...snapshot } };
    this._slotSaving = false;
    this._slotSaveError = "";
    this._slotSaveMessage = "";
    this._slotDiscardPrompt = false;
    this._slotAwaitingRefresh = null;
    this._dialog = { type, key };
  }

  ensureSlotEditor(key, label = "") {
    if (this._slotEditDraft?.key === key && this._slotEditOriginal?.key === key) return;
    const snapshot = this.scheduleSlotSnapshot(key, label);
    this._slotEditOriginal = { key, label, values: { ...snapshot } };
    this._slotEditDraft = { key, label, values: { ...snapshot } };
  }

  resetSlotEditor() {
    this._slotEditOriginal = null;
    this._slotEditDraft = null;
    this._slotSaving = false;
    this._slotSaveError = "";
    this._slotSaveMessage = "";
    this._slotDiscardPrompt = false;
    this._slotAwaitingRefresh = null;
  }

  slotEditDirty() {
    if (!this._slotEditOriginal || !this._slotEditDraft) return false;
    const original = this.normalizedSlotEdit(this._slotEditOriginal.values);
    const draft = this.normalizedSlotEdit(this._slotEditDraft.values);
    return this.slotEditFields().some((field) => original[field] !== draft[field]);
  }

  updateSlotDraftField(field, value) {
    if (!this._slotEditDraft || !this.slotEditFields().includes(field)) return;
    const previousMode = this._slotEditDraft.values.mode;
    this._slotEditDraft.values[field] = this.normalizeSlotEditValue(field, value);
    this._slotSaveError = "";
    if (field === "mode" && previousMode !== this._slotEditDraft.values.mode) {
      this._slotEditDraft.values.enabled = true;
      this.applyProfileToSlotDraft(this._slotEditDraft.values.mode, false);
    }
  }

  applyProfileToSlotDraft(mode, explicitReload = false) {
    if (!this._slotEditDraft) return;
    const values = this._slotEditDraft.values;
    if (mode === "Normalna Praca") {
      const profile = this.normalProfileStoredValues();
      ["physical_work_mode", "sell_power", "discharge_current", "charge_current", "grid_charge_current", "tou_soc"].forEach((field) => {
        if (profile[field] !== undefined && profile[field] !== null) values[field] = this.normalizeSlotEditValue(field, profile[field]);
      });
    } else if (mode === "Ładowanie") {
      const profile = this.chargeProfileStoredValues();
      const mapping = {
        charge_current: "charge_current",
        discharge_current: "discharge_current",
        grid_charge_current: "grid_charge_current",
        target_soc: "tou_soc",
      };
      Object.entries(mapping).forEach(([source, target]) => {
        if (profile[source] !== undefined && profile[source] !== null) values[target] = this.normalizeSlotEditValue(target, profile[source]);
      });
      if (explicitReload && profile.grid_charge_enabled !== undefined) {
        values.charge_enabled = Boolean(profile.grid_charge_enabled);
      }
    }
  }

  slotDraftInput(field, unit = "") {
    const value = this._slotEditDraft?.values?.[field];
    return `<label class="field"><input data-slot-draft-field="${field}" type="text" inputmode="decimal" value="${this.escapeHtml(value ?? "")}"><span>${this.escapeHtml(unit)}</span></label>`;
  }

  slotDraftSelect(field, options) {
    const current = this.normalizeSlotEditValue(field, this._slotEditDraft?.values?.[field]);
    return `<select data-slot-draft-field="${field}">${options.map(([value, label]) => `<option value="${this.escapeHtml(value)}" ${this.normalizeSlotEditValue(field, value) === current ? "selected" : ""}>${this.escapeHtml(label)}</option>`).join("")}</select>`;
  }

  validateSlotEditDraft() {
    if (!this._slotEditDraft) return "Brak danych edytowanego slotu.";
    const values = this.normalizedSlotEdit(this._slotEditDraft.values);
    if (!this.slotWorkModes().includes(values.mode)) return "Wybierz poprawny tryb Harmonogramu.";
    if (values.mode === "Normalna Praca" && !["Zero Export To Load", "Zero Export To CT"].includes(values.physical_work_mode)) {
      return "Wybierz fizyczny tryb Deye dla Normalnej Pracy.";
    }
    const limits = {
      sell_power: [0, 100000], discharge_current: [0, 240], charge_current: [0, 240],
      grid_charge_current: [0, 240], minimum_sell_soc: [0, 100], tou_soc: [0, 100],
      min_sell_price: [0, 5],
    };
    for (const [field, [minimum, maximum]] of Object.entries(limits)) {
      const value = values[field];
      if (value === null && field === "tou_soc") continue;
      if (!Number.isFinite(value) || value < minimum || value > maximum) {
        return `Wartość pola ${field} musi mieścić się w zakresie ${minimum}–${maximum}.`;
      }
    }
    return "";
  }

  buildSlotEditPatch() {
    if (!this._slotEditOriginal || !this._slotEditDraft) return null;
    const original = this.normalizedSlotEdit(this._slotEditOriginal.values);
    const draft = this.normalizedSlotEdit(this._slotEditDraft.values);
    const patch = { slot_key: this._slotEditDraft.key };
    this.slotEditFields().forEach((field) => {
      if (original[field] === draft[field]) return;
      if (field === "physical_work_mode" && draft.mode !== "Normalna Praca") return;
      if (field === "tou_soc" && draft[field] === null) return;
      patch[field] = draft[field];
    });
    // Every real save reasserts the canonical Polish mode.  This migrates a
    // legacy card snapshot on the user's next edit without a separate write.
    if (Object.keys(patch).length > 1) patch.mode = draft.mode;
    return patch;
  }

  slotSnapshotMatchesPatch(key, patch) {
    const label = this._slotEditDraft?.label || this._slotEditOriginal?.label || "";
    const actual = this.normalizedSlotEdit(this.scheduleSlotSnapshot(key, label));
    return Object.entries(patch).every(([field, value]) => field === "slot_key" || actual[field] === this.normalizeSlotEditValue(field, value));
  }

  slotControlEnabled() {
    return this.controlEnabled() && this.controlStatus() !== "Wyłączanie";
  }

  finishSlotSaveAfterRefresh() {
    const localOnly = !this.slotControlEnabled();
    this._slotSaving = false;
    this._saveStatus = "saved";
    this._saveMessage = localOnly
      ? "Zmiany zapisano w Harmonogramie. Sterowanie Deye jest wyłączone — nie wysłano ich do falownika."
      : "Zmiany zapisano w Harmonogramie.";
    this._slotEditOriginal = null;
    this._slotEditDraft = null;
    this._slotAwaitingRefresh = null;
    this._slotDiscardPrompt = false;
    this._dialog = null;
    this._interacting = false;
    this.render();
  }

  syncSlotEditorAfterHass() {
    const pending = this._slotAwaitingRefresh;
    if (!pending || !this.slotSnapshotMatchesPatch(pending.key, pending.patch)) return false;
    this.finishSlotSaveAfterRefresh();
    return true;
  }

  async saveScheduleSlotDraft() {
    if (this._slotSaving || !this._slotEditDraft) return false;
    if (!this.slotEditDirty()) {
      this.resetSlotEditor();
      this._dialog = null;
      this.render();
      return true;
    }
    const validationError = this.validateSlotEditDraft();
    if (validationError) {
      this._slotSaveError = validationError;
      this.renderDialogOnly();
      return false;
    }
    const patch = this.buildSlotEditPatch();
    if (!patch || Object.keys(patch).length === 1) return false;
    this._slotSaving = true;
    this._slotSaveError = "";
    this._slotSaveMessage = "";
    this.renderDialogOnly();
    const success = await this.applySchedulePatch([patch]);
    if (!success) {
      this._slotSaving = false;
      this._slotSaveError = this._saveMessage || "Nie udało się zapisać Harmonogramu";
      this.renderDialogOnly();
      return false;
    }
    this._slotAwaitingRefresh = { key: this._slotEditDraft.key, patch };
    if (!this.syncSlotEditorAfterHass()) this.renderDialogOnly();
    return true;
  }

  cancelScheduleSlotEdit() {
    if (this._slotSaving) return false;
    this.resetSlotEditor();
    this._dialog = null;
    this.render();
    return true;
  }

  discardScheduleSlotChanges() {
    return this.cancelScheduleSlotEdit();
  }

  returnToScheduleSlotEditing() {
    this._slotDiscardPrompt = false;
    this.renderDialogOnly();
  }

  _numericOrNull(value) {
    if (value === null || value === undefined) return null;
    const str = String(value).trim();
    if (str === "") return null;
    const lower = str.toLowerCase();
    if (lower === "unknown" || lower === "unavailable" || lower === "none" || lower === "null") return null;
    const num = Number(str.replace(",", "."));
    return Number.isFinite(num) ? num : null;
  }

  normalProfileNumericValue(entitySuffix, profileKey) {
    const draft = this._normalProfileDraft[profileKey];
    if (Object.prototype.hasOwnProperty.call(this._normalProfileDraft, profileKey)) {
      const draftNum = this._numericOrNull(draft);
      return draftNum !== null ? String(draftNum) : "";
    }
    if (this._normalProfilePending) {
      const pendingNum = this._numericOrNull(this._normalProfilePending[profileKey]);
      if (pendingNum !== null) return String(pendingNum);
    }
    const stored = this.normalProfileStoredValues()[profileKey];
    const storedNum = this._numericOrNull(stored);
    if (storedNum !== null) return String(storedNum);
    const entityId = this.entity("number", entitySuffix);
    const state = this.displayState(entityId, "");
    const known = state && !["unknown", "unavailable", "None", "null"].includes(state);
    return known ? state : "";
  }

  chargeProfileStoredValues() {
    const statusId = this.entity("sensor", "manager_status");
    const profile = this._hass?.states?.[statusId]?.attributes?.charge_profile;
    return profile && typeof profile === "object" ? profile : {};
  }

  chargeProfileNumericValue(entitySuffix, profileKey) {
    const draft = this._chargeProfileDraft[profileKey];
    if (Object.prototype.hasOwnProperty.call(this._chargeProfileDraft, profileKey)) {
      const draftNum = this._numericOrNull(draft);
      return draftNum !== null ? String(draftNum) : "";
    }
    if (this._chargeProfilePending) {
      const pendingNum = this._numericOrNull(this._chargeProfilePending[profileKey]);
      if (pendingNum !== null) return String(pendingNum);
    }
    const stored = this.chargeProfileStoredValues()[profileKey];
    const storedNum = this._numericOrNull(stored);
    if (storedNum !== null) return String(storedNum);
    const entityId = this.entity("number", entitySuffix);
    const state = this.displayState(entityId, "");
    const known = state && !["unknown", "unavailable", "None", "null"].includes(state);
    return known ? state : "brak";
  }

  chargeProfileGridEnabled() {
    if (typeof this._chargeProfileGridDraft === "boolean") return this._chargeProfileGridDraft;
    if (this._chargeProfilePending) return Boolean(this._chargeProfilePending.grid_charge_enabled);
    const stored = this.chargeProfileStoredValues().grid_charge_enabled;
    if (typeof stored === "boolean") return stored;
    const state = this.displayState(this.entity("switch", "charge_profile_grid_enabled"), "");
    if (state === "on" || state === "off") return state === "on";
    return false;
  }

  chargeProfileValues() {
    return {
      chargeCurrent: this.chargeProfileNumericValue("charge_profile_charge_current", "charge_current"),
      dischargeCurrent: this.chargeProfileNumericValue("charge_profile_discharge_current", "discharge_current"),
      gridChargeCurrent: this.chargeProfileNumericValue("charge_profile_grid_charge_current", "grid_charge_current"),
      targetSoc: this.chargeProfileNumericValue("charge_profile_target_soc", "target_soc"),
      gridEnabled: this.chargeProfileGridEnabled(),
    };
  }

  normalProfileValues() {
    return {
      sellPower: this.normalProfileNumericValue("normal_profile_sell_power", "sell_power"),
      dischargeCurrent: this.normalProfileNumericValue("normal_profile_discharge_current", "discharge_current"),
      chargeCurrent: this.normalProfileNumericValue("normal_profile_charge_current", "charge_current"),
      gridChargeCurrent: this.normalProfileNumericValue("normal_profile_grid_charge_current", "grid_charge_current"),
      touSoc: this.normalProfileNumericValue("normal_profile_tou_soc", "tou_soc"),
    };
  }

  normalProfileMode() {
    const draft = this._normalProfileDraft.physical_work_mode;
    if (draft) return this.canonicalNormalProfileMode(draft);
    const pending = this._normalProfilePending?.physical_work_mode;
    if (pending) return this.canonicalNormalProfileMode(pending);
    const stored = this.normalProfileStoredValues().physical_work_mode;
    if (stored) return this.canonicalNormalProfileMode(stored);
    const state = this.displayState(this.entity("select", "normal_profile_mode"), "");
    return state && !["unknown", "unavailable", "None", "null"].includes(state)
      ? this.canonicalNormalProfileMode(state)
      : "";
  }

  _normalProfilePendingMatches(statusProfile) {
    if (!this._normalProfilePending || !statusProfile || typeof statusProfile !== "object") return false;
    const keys = ["physical_work_mode", "sell_power", "discharge_current", "charge_current", "grid_charge_current", "tou_soc"];
    for (const key of keys) {
      const pending = this._normalProfilePending[key];
      const stored = statusProfile[key];
      if (key === "physical_work_mode") {
        if (pending !== stored) return false;
      } else {
        const pendingNum = this._numericOrNull(pending);
        const storedNum = this._numericOrNull(stored);
        if (pendingNum === null && storedNum === null) continue;
        if (pendingNum === null || storedNum === null) return false;
        if (Math.abs(pendingNum - storedNum) > 0.05) return false;
      }
    }
    return true;
  }

  checkNormalProfilePending() {
    if (!this._normalProfilePending) return;
    const statusId = this.entity("sensor", "manager_status");
    const statusProfile = this._hass?.states?.[statusId]?.attributes?.normal_profile;
    if (statusProfile && typeof statusProfile === "object" && this._normalProfilePendingMatches(statusProfile)) {
      this._normalProfilePending = null;
    }
  }

  _chargeProfilePendingMatches(statusProfile) {
    if (!this._chargeProfilePending || !statusProfile || typeof statusProfile !== "object") return false;
    const keys = ["grid_charge_enabled", "charge_current", "discharge_current", "grid_charge_current", "target_soc"];
    for (const key of keys) {
      const pending = this._chargeProfilePending[key];
      const stored = statusProfile[key];
      if (key === "grid_charge_enabled") {
        if (Boolean(pending) !== Boolean(stored)) return false;
      } else {
        const pendingNum = this._numericOrNull(pending);
        const storedNum = this._numericOrNull(stored);
        if (pendingNum === null || storedNum === null) return false;
        if (Math.abs(pendingNum - storedNum) > 0.05) return false;
      }
    }
    return true;
  }

  checkChargeProfilePending() {
    if (!this._chargeProfilePending) return;
    const statusId = this.entity("sensor", "manager_status");
    const statusProfile = this._hass?.states?.[statusId]?.attributes?.charge_profile;
    if (statusProfile && typeof statusProfile === "object" && this._chargeProfilePendingMatches(statusProfile)) {
      this._chargeProfilePending = null;
    }
  }

  syncNormalProfileControls() {
    if (!this._dialog || this._dialog.type !== "settings") return;
    const modeSelect = this.querySelector('[data-raw="normal-profile-mode"]');
    if (modeSelect && !this._normalProfileDraft.physical_work_mode) {
      const value = this.normalProfileMode();
      if (value && modeSelect.value !== value) modeSelect.value = value;
    }
    this.querySelectorAll("[data-normal-profile-number]").forEach((el) => {
      const key = el.dataset.normalProfileNumber;
      if (Object.prototype.hasOwnProperty.call(this._normalProfileDraft, key)) return;
      const value = this.normalProfileNumericValue(`normal_profile_${key}`, key);
      if (value !== el.value) el.value = value;
    });
  }

  chargeProfileValues() {
    return {
      chargeCurrent: this.chargeProfileNumericValue("charge_profile_charge_current", "charge_current"),
      dischargeCurrent: this.chargeProfileNumericValue("charge_profile_discharge_current", "discharge_current"),
      gridChargeCurrent: this.chargeProfileNumericValue("charge_profile_grid_charge_current", "grid_charge_current"),
      targetSoc: this.chargeProfileNumericValue("charge_profile_target_soc", "target_soc"),
      gridEnabled: this.chargeProfileGridEnabled(),
    };
  }

  callService(domain, service, data = {}) {
    return this._hass.callService(domain, service, data);
  }

  async applySchedulePatch(updates, options = null) {
    if (!Array.isArray(updates) || !updates.length) return false;
    options = options || {};
    if (!this.hasService("deye_energy_manager", "apply_schedule_patch")) {
      this.failSave("schedule_patch", new Error("Usługa apply_schedule_patch jest niedostępna"));
      return false;
    }
    this.beginSave();
    try {
      const payload = options.replaceDay === true
        ? { date: options.date, replace_day: true, updates }
        : updates;
      await this.callService("deye_energy_manager", "apply_schedule_patch", { data: JSON.stringify(payload) });
      if (!this.slotControlEnabled()) {
        this._saveMessage = "Zmiany zapisano w Harmonogramie. Sterowanie Deye jest wyłączone — nie wysłano ich do falownika.";
      }
      this.finishSave();
      return true;
    } catch (error) {
      this.failSave("schedule_patch", error);
      return false;
    }
  }

  async savePhysicalTouSlot(slot) {
    if (this._touSaving || this.touWritePending()) {
      this._touSaveError = "Trwa zapis Deye Time Of Use";
      this.renderDialogOnly();
      return false;
    }
    if (!this.hasService("deye_energy_manager", "set_tou_slot")) {
      this.failSave("tou_slot", new Error("Usługa set_tou_slot jest niedostępna"));
      return false;
    }
    const capability = this.touCapabilityRow(slot);
    if (!capability || capability.read_only === true) {
      this._touSaveError = "Ten provider udostępnia Deye Time Of Use tylko do odczytu.";
      this.renderDialogOnly();
      return false;
    }
    if (this.touControlBlocked(capability)) {
      this._touSaveError = "Sterowanie Deye jest wyłączone.";
      this.renderDialogOnly();
      return false;
    }
    this.collectTouEditorDraft(slot);
    let payload;
    try {
      payload = this.buildTouPartialPayload(slot);
    } catch (error) {
      this._touSaveError = error?.message || String(error);
      this.renderDialogOnly();
      return false;
    }
    if (Object.keys(payload).length === 1) {
      this._touSaveError = "Brak zmian do zapisania.";
      this.renderDialogOnly();
      return false;
    }
    this._touSaving = true;
    this._touSaveError = "";
    this.beginSave();
    this.renderDialogOnly();
    try {
      await this.callService("deye_energy_manager", "set_tou_slot", payload);
      this._touSaving = false;
      const status = this.touOperationStatus();
      if (status === "confirmed") {
        this.finishSave();
        this.refreshTouEditorFromActual(slot);
        this._touAwaitingConfirmation = null;
      } else if (["rollback", "rollback_failed", "mismatch", "unavailable"].includes(status)) {
        this._pendingSaves = Math.max(0, this._pendingSaves - 1);
        this._saveHadError = true;
        this._saveStatus = "error";
        this._touSaveError = this.touOperationError() || this.touOperationStatusLabel(status);
        this.refreshTouEditorFromActual(slot, false);
      } else {
        this._pendingSaves = Math.max(0, this._pendingSaves - 1);
        this._saveStatus = "idle";
        this._touAwaitingConfirmation = slot;
      }
      this.renderDialogOnly();
      return true;
    } catch (error) {
      this._touSaving = false;
      this._touSaveError = error?.message || "Nie udało się zapisać Deye Time Of Use.";
      this.refreshTouEditorFromActual(slot, false);
      this.failSave(`tou_slot_${slot}`, error);
      return false;
    }
  }

  hasService(domain, service) {
    return Boolean(this._hass?.services?.[domain]?.[service]);
  }

  updateSaveIndicator() {
    const el = this.querySelector("[data-save-indicator]");
    if (!el) return;
    el.className = `save-indicator ${this._saveStatus}`;
    el.textContent = this._saveStatus === "saving"
      ? this._saveMessage || "Zapisywanie..."
      : this._saveStatus === "saved"
        ? this._saveMessage || "Zapisano"
        : this._saveStatus === "error"
          ? this._saveMessage || "Błąd zapisu"
          : "";
  }

  updateControlUi() {
    let control = this.controlState();
    const expected = this._controlExpectedEnabled;
    const settled = typeof expected === "boolean"
      && control.enabled === expected
      && control.status !== "Wyłączanie";
    const updateFeedback = this._controlFeedbackActive;
    if (settled) {
      this._controlExpectedEnabled = null;
      control = this.controlState();
    }

    const buttons = typeof this.querySelectorAll === "function"
      ? this.querySelectorAll("[data-control-toggle]")
      : [];
    buttons.forEach((button) => {
      button.textContent = `Sterowanie Deye — ${control.status}`;
      button.disabled = control.pending;
      button.classList?.toggle("active", control.enabled);
    });
    const status = typeof this.querySelector === "function"
      ? this.querySelector("[data-live='control-status']")
      : null;
    if (status) {
      status.textContent = control.status;
      status.className = `mode-${control.enabled ? "normal" : "disabled"}`;
    }

    if (updateFeedback) {
      this._saveStatus = settled ? "saved" : "saving";
      this._saveMessage = settled
        ? (control.enabled ? "Sterowanie Deye jest aktywne." : "Sterowanie Deye jest wyłączone.")
        : (expected === true ? "Włączanie Sterowania Deye…" : "Wyłączanie Sterowania Deye…");
      if (typeof this.querySelector === "function") this.updateSaveIndicator();
      if (settled) this._controlFeedbackActive = false;
    }
  }

  beginSave() {
    window.clearTimeout(this._saveStatusTimer);
    if (this._pendingSaves === 0) this._saveHadError = false;
    this._pendingSaves += 1;
    this._saveStatus = "saving";
    this._saveMessage = "";
    this.updateSaveIndicator();
  }

  finishSave() {
    this._pendingSaves = Math.max(0, this._pendingSaves - 1);
    if (this._pendingSaves > 0) return;
    if (this._saveHadError) {
      this._saveStatus = "error";
      this.updateSaveIndicator();
      return;
    }
    this._saveStatus = "saved";
    this.updateSaveIndicator();
    this._saveStatusTimer = window.setTimeout(() => {
      this._saveStatus = "idle";
      this.updateSaveIndicator();
    }, 2500);
  }

  failSave(entityId, error) {
    this._pendingSaves = Math.max(0, this._pendingSaves - 1);
    this._saveHadError = true;
    delete this._optimisticStates[entityId];
    this._saveStatus = "error";
    this._saveMessage = `Błąd zapisu: ${error?.message || "brak potwierdzenia Home Assistant"}`;
    this.captureScrollPositions();
    this.render();
    this.updateSaveIndicator();
  }

  updateDefaultApplyState() {
    this.querySelectorAll("[data-default-action]").forEach((button) => {
      button.disabled = this._defaultsApplying;
      button.textContent = this._defaultsApplying
        ? "Stosowanie ustawień domyślnych…"
        : button.dataset.defaultLabel || "Zastosuj ustawienia domyślne";
    });
    this.querySelectorAll("[data-defaults-status]").forEach((status) => {
      status.className = `hint defaults-status ${this._defaultsStatus}`;
      status.textContent = this._defaultsMessage;
      status.hidden = !this._defaultsMessage;
    });
  }

  optimisticService(entityId, value, domain, service, data) {
    if (!this.exists(entityId)) return Promise.resolve(false);
    this._optimisticStates[entityId] = String(value);
    this.beginSave();
    const request = this.callService(domain, service, data);
    return Promise.resolve(request).then(() => {
      this.finishSave();
      window.setTimeout(() => {
        if (Object.prototype.hasOwnProperty.call(this._optimisticStates, entityId)) {
          delete this._optimisticStates[entityId];
          this.updateToggleButtons();
        }
      }, 15000);
      return true;
    }).catch((error) => {
      this.failSave(entityId, error);
      return false;
    });
  }

  setNumber(entityId, value) {
    const raw = String(value).trim().replace(",", ".");
    if (!raw) return Promise.resolve(false);
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || !this.exists(entityId)) return Promise.resolve(false);
    return this.optimisticService(entityId, parsed, "number", "set_value", { entity_id: entityId, value: parsed });
  }

  async saveChargeProfile() {
    const fields = [...this.querySelectorAll("[data-charge-profile-number]")];
    const values = {};
    for (const field of fields) {
      const value = Number(String(field.value).replace(",", "."));
      if (!Number.isFinite(value)) {
        this.failSave("charge_profile", new Error("Wprowadź poprawne wartości profilu ładowania"));
        return false;
      }
      values[field.dataset.chargeProfileNumber] = value;
    }
    const currentRanges = {
      charge_current: { min: 0, max: 240 },
      discharge_current: { min: 0, max: 240 },
      grid_charge_current: { min: 0, max: 240 },
      target_soc: { min: 0, max: 100 },
    };
    for (const [key, { min, max }] of Object.entries(currentRanges)) {
      if (!(key in values) || values[key] < min || values[key] > max) {
        this.failSave("charge_profile", new Error(`Wartość ${key} musi być między ${min} a ${max}`));
        return false;
      }
    }
    values.grid_charge_enabled = typeof this._chargeProfileGridDraft === "boolean"
      ? this._chargeProfileGridDraft
      : this.rawValue("charge-profile-grid", "off") === "on";
    this._chargeProfilePending = { ...values };
    this.beginSave();
    try {
      await this.callService("deye_energy_manager", "save_charge_profile", values);
      // Helper entities are optional for the template save.  Optimistically
      // update only the ones that actually exist so the UI feels snappy.
      const helpers = {
        charge_current: this.entity("number", "charge_profile_charge_current"),
        discharge_current: this.entity("number", "charge_profile_discharge_current"),
        grid_charge_current: this.entity("number", "charge_profile_grid_charge_current"),
        target_soc: this.entity("number", "charge_profile_target_soc"),
        grid_charge_enabled: this.entity("switch", "charge_profile_grid_enabled"),
      };
      Object.entries(values).forEach(([key, value]) => {
        const entityId = helpers[key];
        if (entityId && this.exists(entityId)) {
          this._optimisticStates[entityId] = key === "grid_charge_enabled"
            ? (value ? "on" : "off")
            : String(value);
        }
      });
      this._chargeProfileDraft = {};
      this._chargeProfileGridDraft = null;
      this.finishSave();
      this.captureScrollPositions();
      this.render();
      return true;
    } catch (error) {
      this._chargeProfilePending = null;
      this.failSave("charge_profile", error);
      return false;
    }
  }

  async saveNormalProfile() {
    const physical_work_mode = this.rawValue("normal-profile-mode", "");
    if (!physical_work_mode) {
      this.failSave("normal_profile", new Error("Nie wybrano fizycznego trybu Deye dla normalnej pracy"));
      return false;
    }
    const fields = [...this.querySelectorAll("[data-normal-profile-number]")];
    const values = { physical_work_mode };
    for (const field of fields) {
      const raw = String(field.value).trim();
      if (raw === "") {
        this.failSave("normal_profile", new Error("Wprowadź poprawne wartości profilu normalnej pracy"));
        return false;
      }
      const value = Number(raw.replace(",", "."));
      if (!Number.isFinite(value)) {
        this.failSave("normal_profile", new Error("Wprowadź poprawne wartości profilu normalnej pracy"));
        return false;
      }
      values[field.dataset.normalProfileNumber] = value;
    }
    if (values.tou_soc === undefined || values.tou_soc < 0 || values.tou_soc > 100) {
      this.failSave("normal_profile", new Error("Brak poprawnej wartości SOC baterii Deye TOU"));
      return false;
    }
    this._normalProfilePending = { ...values };
    this.beginSave();
    try {
      await this.callService("deye_energy_manager", "save_normal_profile", values);
      this._normalProfileDraft = {};
      this.finishSave();
      this.captureScrollPositions();
      this.render();
      return true;
    } catch (error) {
      this._normalProfilePending = null;
      this.failSave("normal_profile", error);
      return false;
    }
  }

  async reloadNormalProfileSlot(slotKey) {
    if (!slotKey) return false;
    this.beginSave();
    try {
      await this.callService("deye_energy_manager", "apply_schedule_patch", {
        data: JSON.stringify([{
          slot_key: slotKey,
          mode: "Normalna Praca",
          force_copy_normal_profile: true,
        }]),
      });
      this.finishSave();
      this.captureScrollPositions();
      this.render();
      return true;
    } catch (error) {
      this.failSave("schedule_patch", error);
      return false;
    }
  }

  async reloadChargeProfileSlot(slotKey) {
    if (!slotKey) return false;
    this.beginSave();
    try {
      await this.callService("deye_energy_manager", "apply_schedule_patch", {
        data: JSON.stringify([{
          slot_key: slotKey,
          mode: "Ładowanie",
          force_copy_charge_profile: true,
        }]),
      });
      this.finishSave();
      this.captureScrollPositions();
      this.render();
      return true;
    } catch (error) {
      this.failSave("schedule_patch", error);
      return false;
    }
  }

  setSelect(entityId, option) {
    if (!this.exists(entityId)) return Promise.resolve(false);
    // The mode never implies permission to charge from the grid.  That
    // permission is controlled solely by „Ładowanie z sieci” in the shared
    // Profil Ładowania.
    const request = this.optimisticService(entityId, option, "select", "select_option", { entity_id: entityId, option });
    if (this._scheduleEntityIds?.includes(entityId)) {
      this.captureScrollPositions();
      this.render();
    }
    return request;
  }

  turnSwitch(entityId, value) {
    if (!this.exists(entityId)) return Promise.resolve(false);
    const target = value ? "on" : "off";
    this._optimisticStates[entityId] = target;
    this.updateToggleButtons();
    return this.optimisticService(entityId, target, "switch", value ? "turn_on" : "turn_off", { entity_id: entityId });
  }

  setTime(entityId, value) {
    if (!this.exists(entityId)) return Promise.resolve(false);
    const time = value.length === 5 ? `${value}:00` : value;
    return this.optimisticService(entityId, time, "time", "set_value", { entity_id: entityId, time });
  }

  updatePillElement(el) {
    const entityId = el.dataset.toggle;
    const state = this.displayState(entityId, "brak");
    el.classList.toggle("on", state === "on");
    el.classList.toggle("off", state === "off");
    el.classList.toggle("missing", state !== "on" && state !== "off");
    el.textContent = state === "on" ? "tak" : state === "off" ? "nie" : "brak";
  }

  updateToggleButtons() {
    this.querySelectorAll("[data-toggle]").forEach((el) => this.updatePillElement(el));
  }

  toggle(entityId) {
    const entity = this._hass.states[entityId];
    if (!entity) return;
    const turnOn = this.displayState(entityId, entity.state) !== "on";
    const target = turnOn ? "on" : "off";
    this.captureScrollPositions();
    this.turnSwitch(entityId, turnOn);
    this.render();
    window.setTimeout(() => {
      if (this._optimisticStates?.[entityId] === target) {
        delete this._optimisticStates[entityId];
        this.updateToggleButtons();
      }
    }, 12000);
  }

  async toggleControl() {
    const control = this.controlState();
    if (control.pending) return false;
    const entityId = control.entity_id;
    const entity = entityId ? this._hass?.states?.[entityId] : null;
    if (!entity || ["unavailable", "unknown"].includes(String(entity.state))) {
      this._controlError = "Nie znaleziono encji Sterowanie Deye. Przeładuj integrację lub sprawdź konfigurację.";
      this._saveStatus = "error";
      this._saveMessage = this._controlError;
      this.render();
      return false;
    }

    const turnOn = !control.enabled;
    this._controlExpectedEnabled = turnOn;
    this._controlFeedbackActive = true;
    this._controlTogglePending = true;
    this._controlError = "";
    this._saveStatus = "saving";
    this._saveMessage = turnOn ? "Włączanie Sterowania Deye…" : "Wyłączanie Sterowania Deye…";
    this.render();
    try {
      await this.callService("switch", turnOn ? "turn_on" : "turn_off", { entity_id: entityId });
      return true;
    } catch (error) {
      this._controlExpectedEnabled = null;
      this._controlFeedbackActive = false;
      this._controlError = `Nie udało się przełączyć Sterowania Deye: ${error?.message || error}`;
      this._saveStatus = "error";
      this._saveMessage = this._controlError;
      return false;
    } finally {
      this._controlTogglePending = false;
      this.render();
      this.updateControlUi();
    }
  }

  pill(entityId, text = null) {
    const state = this.displayState(entityId, "brak");
    const cls = state === "on" ? "on" : state === "off" ? "off" : "missing";
    const label = text || (state === "on" ? "tak" : state === "off" ? "nie" : "brak");
    return `<button class="pill ${cls}" data-toggle="${entityId}" ${this.exists(entityId) ? "" : "disabled"}>${label}</button>`;
  }

  selectInput(entityId, fallbackOptions = []) {
    const current = this.displayState(entityId, "");
    const options = this.options(entityId, fallbackOptions);
    const merged = options.includes(current) || !current ? options : [current, ...options];
    return `<select data-select="${entityId}" ${this.exists(entityId) ? "" : "disabled"}>
      ${merged.map((option) => `<option value="${this.escapeHtml(option)}" ${option === current ? "selected" : ""}>${this.escapeHtml(this.slotModeLabel(option))}</option>`).join("")}
    </select>`;
  }

  numberInput(entityId, unit = "") {
    return `<label class="field">
      <input data-number="${this.escapeHtml(entityId)}" type="text" inputmode="decimal" value="${this.escapeHtml(this.numberState(entityId))}" ${this.exists(entityId) ? "" : "disabled"}>
      <span>${this.escapeHtml(unit)}</span>
    </label>`;
  }

  touSocInput(entityId) {
    // A missing physical TOU SOC is intentionally not shown as zero.  Zero is
    // valid only when the user explicitly enters it and the Deye entity allows
    // it; migration never guesses this physical setting.
    const state = this.displayState(entityId, "");
    const known = state && !["unknown", "unavailable", "None", "null"].includes(state);
    return `<label class="field">
      <input data-number="${this.escapeHtml(entityId)}" type="text" inputmode="decimal" value="${this.escapeHtml(known ? state : "")}" placeholder="wymaga potwierdzenia" ${this.exists(entityId) ? "" : "disabled"}>
      <span>%</span>
    </label>`;
  }

  chargeProfileInput(name, entityId, unit = "") {
    const entity = this._hass.states[entityId];
    const profile = this.chargeProfileValues();
    const profileKeys = { charge_current: "chargeCurrent", discharge_current: "dischargeCurrent", grid_charge_current: "gridChargeCurrent", target_soc: "targetSoc" };
    const fallback = name === "target_soc" ? { min: 0, max: 100, step: 1 } : { min: 0, max: 240, step: 1 };
    const current = entity && !["unknown", "unavailable", ""].includes(entity.state) ? entity.state : profile[profileKeys[name]];
    const value = Object.prototype.hasOwnProperty.call(this._chargeProfileDraft, name) ? this._chargeProfileDraft[name] : current;
    const rawMin = Number(entity?.attributes?.min);
    const rawMax = Number(entity?.attributes?.max);
    const rawStep = Number(entity?.attributes?.step);
    const min = Number.isFinite(rawMin) ? rawMin : fallback.min;
    const max = Number.isFinite(rawMax) ? rawMax : fallback.max;
    const step = Number.isFinite(rawStep) && rawStep > 0 ? rawStep : fallback.step;
    return `<label class="field">
      <input data-charge-profile-number="${this.escapeHtml(name)}" type="number" inputmode="decimal" value="${this.escapeHtml(value ?? "")}" min="${min}" max="${max}" step="${step}">
      <span>${this.escapeHtml(unit)}</span>
    </label>`;
  }

  defaultProfileInput(name, entityId, unit = "") {
    const entity = this._hass.states[entityId];
    const current = entity && !["unknown", "unavailable"].includes(entity.state) ? entity.state : "";
    const value = Object.prototype.hasOwnProperty.call(this._defaultSettingsDraft, name)
      ? this._defaultSettingsDraft[name] : current;
    const min = Number(entity?.attributes?.min);
    const max = Number(entity?.attributes?.max);
    const step = Number(entity?.attributes?.step);
    const range = Number.isFinite(min) && Number.isFinite(max) && Number.isFinite(step) && step > 0;
    return `<label class="field"><input data-default-profile-number="${this.escapeHtml(name)}" type="number" inputmode="decimal" value="${this.escapeHtml(value)}" ${range ? `min="${min}" max="${max}" step="${step}"` : ""} ${this.exists(entityId) && current !== "" && range ? "" : "disabled"}><span>${this.escapeHtml(unit)}</span></label>`;
  }

  normalProfileInput(name, entityId, unit = "") {
    const profile = this.normalProfileValues();
    const profileKeys = {
      sell_power: "sellPower",
      discharge_current: "dischargeCurrent",
      charge_current: "chargeCurrent",
      grid_charge_current: "gridChargeCurrent",
      tou_soc: "touSoc",
    };
    const fallback = {
      sell_power: { min: 0, max: this.effectiveInverterMaxPowerW(), step: 1 },
      discharge_current: { min: 0, max: 240, step: 0.1 },
      charge_current: { min: 0, max: 240, step: 0.1 },
      grid_charge_current: { min: 0, max: 240, step: 0.1 },
      tou_soc: { min: 0, max: 100, step: 1 },
    };
    const current = profile[profileKeys[name]];
    const value = Object.prototype.hasOwnProperty.call(this._normalProfileDraft, name)
      ? this._normalProfileDraft[name] : current;
    const entity = this._hass.states[entityId];
    const rawMin = Number(entity?.attributes?.min);
    const rawMax = Number(entity?.attributes?.max);
    const rawStep = Number(entity?.attributes?.step);
    const fb = fallback[name] || { min: 0, max: 100, step: 1 };
    const min = Number.isFinite(rawMin) ? rawMin : fb.min;
    const max = Number.isFinite(rawMax) ? rawMax : fb.max;
    const step = Number.isFinite(rawStep) && rawStep > 0 ? rawStep : fb.step;
    return `<label class="field"><input data-normal-profile-number="${this.escapeHtml(name)}" type="number" inputmode="decimal" value="${this.escapeHtml(value ?? "")}" min="${min}" max="${max}" step="${step}"><span>${this.escapeHtml(unit)}</span></label>`;
  }

  async saveDefaultSettings() {
    const mode = this.rawValue("default-work-mode", "");
    const physical_work_mode = this.rawValue("default-physical-work-mode", "");
    if (!this.defaultWorkModes().includes(mode)) {
      this.failSave("default_settings", new Error("Wybierz poprawny logiczny tryb domyślny"));
      return false;
    }
    if (mode === "Normalna Praca" && !physical_work_mode) {
      this.failSave("default_settings", new Error("Wybierz fizyczny wariant Normalnej Pracy"));
      return false;
    }
    const values = { mode };
    if (physical_work_mode) values.physical_work_mode = physical_work_mode;
    for (const field of this.querySelectorAll("[data-default-profile-number]")) {
      const value = Number(String(field.value).replace(",", "."));
      if (!Number.isFinite(value)) {
        this.failSave("default_settings", new Error("Wprowadź poprawne wartości ustawień domyślnych"));
        return false;
      }
      values[field.dataset.defaultProfileNumber] = value;
    }
    this.beginSave();
    try {
      await this.callService("deye_energy_manager", "save_default_settings", values);
      this._defaultSettingsDraft = {};
      this.finishSave();
      return true;
    } catch (error) {
      this.failSave("default_settings", error);
      return false;
    }
  }

  rawSelect(name, options = [], value = "") {
    return `<select data-raw="${name}">
      ${options.map((option) => {
        const optionValue = Array.isArray(option) ? option[0] : option;
        const optionLabel = Array.isArray(option) ? option[1] : option;
        return `<option value="${this.escapeHtml(optionValue)}" ${optionValue === value ? "selected" : ""}>${this.escapeHtml(optionLabel)}</option>`;
      }).join("")}
    </select>`;
  }

  rawNumber(name, value = 0, unit = "") {
    return `<label class="field">
      <input data-raw="${this.escapeHtml(name)}" type="text" inputmode="decimal" value="${this.escapeHtml(value)}">
      <span>${this.escapeHtml(unit)}</span>
    </label>`;
  }

  rawValue(name, fallback = "") {
    return this.querySelector(`[data-raw="${name}"]`)?.value ?? fallback;
  }

  aiDefaults() {
    return {
      enabled: true,
      mode: "proposal",
      strategy: "balanced",
      forecastEnabled: true,
      forecastMargin: 10,
      realPv: true,
      history: true,
      prices: true,
      minSellPrice: 0.2,
      maxBuyPrice: 0.7,
      minSoc: 20,
      targetSoc: 80,
      batteryCapacityKwh: 10,
      batteryEfficiency: 90,
      reserveKwh: 2,
      maxSellPower: 5000,
      minimumAutoSellPowerW: 1000,
      priceEquivalenceBand: 0.05,
      gridExportLimit: 5000,
      maxDischargeCurrent: 120,
      maxChargeCurrent: 120,
      maxGridChargeCurrent: 60,
      allowGridCharge: true,
      allowBatterySell: true,
      allowDeyeMode: true,
    };
  }

  aiSettings() {
    const defaults = this.aiDefaults();
    if (this._aiSettingsCache) return { ...defaults, ...this._aiSettingsCache };
    const entity = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const backend = entity?.attributes?.settings;
    if (backend && typeof backend === "object" && !Array.isArray(backend) && Object.keys(backend).length) {
      return { ...defaults, ...backend };
    }
    try {
      const saved = JSON.parse(localStorage.getItem("deye_energy_manager_ai_settings_v073") || "{}");
      return { ...defaults, ...saved };
    } catch (_err) {
      return defaults;
    }
  }

  saveAiSettings(settings) {
    this._aiSettingsCache = { ...settings };
    try {
      localStorage.setItem("deye_energy_manager_ai_settings_v073", JSON.stringify(settings));
    } catch (_err) {
      // LocalStorage can be blocked in some HA webviews. In that case the UI still works for this render.
    }
    window.clearTimeout(this._aiSettingsSaveTimer);
    this._aiSettingsSaveTimer = window.setTimeout(() => {
      this.callService("deye_energy_manager", "save_ai_settings", { data: JSON.stringify(this._aiSettingsCache) });
    }, 400);
  }

  aiHistory() {
    if (this._aiHistoryCache) return this._aiHistoryCache;
    const entity = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const backend = entity?.attributes?.history;
    if (Array.isArray(backend)) return backend;
    try {
      const history = JSON.parse(localStorage.getItem("deye_energy_manager_ai_history_v073") || "[]");
      return Array.isArray(history) ? history : [];
    } catch (_err) {
      return [];
    }
  }

  saveAiAnalysis(ai, event = "suggestion", extra = {}) {
    try {
      const now = Date.now();
      const entry = {
        timestamp: now,
        event,
        bestSell: ai.bestSell.slice(0, 3),
        cheapBuy: ai.cheapBuy.slice(0, 3),
        cheapBuy48: (ai.cheapBuy48 || []).slice(0, 6),
        tariff: {
          provider: ai.tariff?.provider,
          plan: ai.tariff?.plan,
          catalog_version: ai.tariff?.catalog_version,
        },
        solcastToday: ai.solcastToday,
        solcastRemaining: ai.solcastRemaining,
        dailyPv: ai.dailyPv,
        forecastTodayKwh: ai.solcastMetrics?.forecast_today_kwh ?? ai.solcastToday,
        productionTodayKwh: ai.solcastMetrics?.production_today_kwh ?? ai.dailyPv,
        remainingForecastKwh: ai.solcastMetrics?.remaining_forecast_kwh ?? ai.solcastRemaining,
        realizationTodayPct: ai.solcastMetrics?.realization_today_pct ?? null,
        historicalAccuracyPct: ai.solcastMetrics?.historical_accuracy_pct ?? ai.learning?.solcast_accuracy_avg ?? null,
        forecastTomorrowKwh: ai.solcastMetrics?.forecast_tomorrow_kwh ?? null,
        forecastCorrection: ai.forecastCorrection,
        weatherRiskFactor: ai.weatherRiskFactor,
        learningDays: ai.learning?.recorded_days || 0,
        learningHours: ai.learning?.recorded_hours || 0,
        solcastAccuracy: ai.solcastMetrics?.historical_accuracy_pct ?? ai.learning?.solcast_accuracy_avg ?? null,
        expectedRemainingLoad: ai.expectedRemainingLoad,
        estimatedSurplus: ai.estimatedSurplus,
        predictedSoc: ai.predictedSoc,
        predictedSocTrend: ai.predictedSocTrend,
        activeConfigured: ai.activeConfigured,
        strategy: ai.settings.strategy,
        maxSellPower: ai.settings.maxSellPower,
        minSoc: ai.settings.minSoc,
        forecastMargin: ai.settings.forecastMargin,
        ...extra,
      };
      entry.fingerprint = JSON.stringify({
        event,
        bestSell: entry.bestSell,
        cheapBuy: entry.cheapBuy,
        strategy: entry.strategy,
        activeConfigured: entry.activeConfigured,
        predictedSocTrend: entry.predictedSocTrend,
        forecastCorrection: Math.round((entry.forecastCorrection || 0) * 20) / 20,
        estimatedSurplus: Math.round((entry.estimatedSurplus || 0) * 2) / 2,
      });
      const history = this.aiHistory();
      const latest = history.find((item) => (item.event || "suggestion") === "suggestion");
      if (event === "suggestion" && latest?.fingerprint === entry.fingerprint) return;
      const updated = [entry, ...history].slice(0, 365);
      this._aiHistoryCache = updated;
      this.callService("deye_energy_manager", "save_ai_analysis", { data: JSON.stringify(entry) });
      localStorage.setItem("deye_energy_manager_ai_history_v073", JSON.stringify(updated));
    } catch (_err) {
      // Historia jest pomocnicza i może być niedostępna w części webview Home Assistant.
    }
  }

  clearAiHistory() {
    this._aiHistoryCache = [];
    this.callService("deye_energy_manager", "clear_ai_history", {});
    try {
      localStorage.removeItem("deye_energy_manager_ai_history_v073");
    } catch (_err) {
      // Brak dostępu do localStorage nie powinien blokować karty.
    }
  }

  historyData() {
    const entity = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const attrs = entity?.attributes || {};
    return {
      analyses: this.aiHistory(),
      daily: Array.isArray(attrs.daily_summary) ? attrs.daily_summary : [],
      monthly: Array.isArray(attrs.monthly_summary) ? attrs.monthly_summary : [],
      solcast: Array.isArray(attrs.solcast_history) ? attrs.solcast_history : [],
    };
  }

  escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  }

  filteredAnalyses() {
    const { analyses } = this.historyData();
    const filters = this._historyFilters || {};
    return analyses.filter((item) => {
      const date = new Date(Number(item.timestamp) || item.date || 0);
      const day = Number.isNaN(date.getTime()) ? String(item.date || "") : date.toISOString().slice(0, 10);
      if (filters.from && day < filters.from) return false;
      if (filters.to && day > filters.to) return false;
      return !filters.type || filters.type === "all" || (item.event || "suggestion") === filters.type;
    });
  }

  downloadHistory(filename, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  exportHistory(format) {
    const data = this.historyData();
    const stamp = new Date().toISOString().slice(0, 10);
    if (format === "json") {
      this.downloadHistory(`deye-historia-${stamp}.json`, JSON.stringify(data, null, 2), "application/json");
      return;
    }
    const rows = [["typ", "data", "pv_kwh", "zuzycie_kwh", "import_kwh", "eksport_kwh", "sprzedaz_kwh", "wartosc_pln", "prognoza_kwh", "trafnosc_pct"]];
    data.daily.forEach((item) => rows.push(["dzien", item.date, item.pv_kwh, item.load_kwh, item.grid_import_kwh, item.grid_export_kwh, item.sold_kwh, item.sold_value, item.forecast_kwh, item.accuracy_percent]));
    data.analyses.forEach((item) => rows.push([item.event || "suggestion", new Date(item.timestamp).toISOString(), item.dailyPv, item.expectedRemainingLoad, "", "", "", "", item.solcastToday, item.solcastAccuracy]));
    const csv = rows.map((row) => row.map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`).join(";")).join("\n");
    this.downloadHistory(`deye-historia-${stamp}.csv`, csv, "text/csv;charset=utf-8");
  }

  exportMonthlyReport() {
    const rows = [["miesiac", "dni", "pv_kwh", "zuzycie_kwh", "import_kwh", "eksport_kwh", "sprzedaz_kwh", "wartosc_pln", "prognoza_kwh", "produkcja_kwh"]];
    this.historyData().monthly.forEach((item) => rows.push([item.month, item.days, item.pv_kwh, item.load_kwh, item.grid_import_kwh, item.grid_export_kwh, item.sold_kwh, item.sold_value, item.forecast_kwh, item.actual_kwh]));
    const csv = rows.map((row) => row.map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`).join(";")).join("\n");
    this.downloadHistory(`deye-raport-miesieczny-${new Date().toISOString().slice(0, 7)}.csv`, csv, "text/csv;charset=utf-8");
  }

  editableConfigEntities() {
    const editableDomains = new Set(["number", "select", "switch", "time", "input_number", "input_select", "input_boolean", "input_datetime"]);
    return Object.keys(this._hass?.states || {}).filter((entityId) => {
      const [domain] = entityId.split(".");
      return editableDomains.has(domain) && entityId.includes("deye_energy_manager_");
    });
  }

  configurationSnapshot() {
    const values = {};
    this.editableConfigEntities().forEach((entityId) => { values[entityId] = this.state(entityId); });
    const tariff = this.tariffData();
    return {
      format: "deye-energy-manager-config",
      version: "0.8.0",
      created_at: new Date().toISOString(),
      values,
      physical_tou: this.physicalTouDiagnostics().map((row) => ({
        slot: Number(row.range),
        start: String(row.actual_start || "").slice(0, 5),
        end: String(row.actual_end || "").slice(0, 5),
        soc: this.asNumber(row.actual_soc),
        grid_charge: row.actual_grid_charge === true,
      })),
      ai_settings: this.aiSettings(),
      tariff_settings: {
        tariff_mode: tariff.mode || "automatic",
        osd_provider: tariff.provider || "pge",
        tariff_plan: tariff.plan || "g11",
        distribution_peak_rate: tariff.peak_rate ?? 0,
        distribution_offpeak_rate: tariff.offpeak_rate ?? 0,
        custom_offpeak_windows: tariff.custom_offpeak_windows || "13:00-15:00,22:00-06:00",
        price_includes_distribution: Boolean(tariff.price_includes_distribution),
        grid_positive_is_import: tariff.grid_positive_is_import !== false,
        battery_positive_is_discharge: tariff.battery_positive_is_discharge !== false,
      },
      card: { theme: this.config?.theme || "deye" },
    };
  }

  async applyConfigurationSnapshot(snapshot) {
    if (!snapshot || snapshot.format !== "deye-energy-manager-config" || typeof snapshot.values !== "object") throw new Error("Nieprawidłowy plik konfiguracji");
    const controlMode = this.entity("select", "control_mode");
    const scheduler = this.entity("switch", "scheduler");
    const chargeScheduler = this.entity("switch", "charge_scheduler");
    const masterControl = this.controlEntityId();
    const deferred = new Set([controlMode, scheduler, chargeScheduler, masterControl].filter(Boolean));
    if (this.exists(controlMode)) {
      await this.callService("select", "select_option", { entity_id: controlMode, option: "Stop Sell" });
    }
    if (this.exists(scheduler)) await this.callService("switch", "turn_off", { entity_id: scheduler });
    if (this.exists(chargeScheduler)) await this.callService("switch", "turn_off", { entity_id: chargeScheduler });
    for (const [entityId, value] of Object.entries(snapshot.values)) {
      if (!entityId.includes("deye_energy_manager_") || !this.exists(entityId) || deferred.has(entityId)) continue;
      const domain = entityId.split(".")[0];
      if (["switch", "input_boolean"].includes(domain)) await this.callService(domain, value === "on" ? "turn_on" : "turn_off", { entity_id: entityId });
      else if (["select", "input_select"].includes(domain)) await this.callService(domain, "select_option", { entity_id: entityId, option: value });
      else if (["number", "input_number"].includes(domain)) await this.callService(domain, "set_value", { entity_id: entityId, value: Number(value) });
      else if (domain === "time") await this.callService(domain, "set_value", { entity_id: entityId, time: String(value).slice(0, 8) });
      else if (domain === "input_datetime") await this.callService(domain, "set_datetime", { entity_id: entityId, time: String(value).slice(0, 8) });
    }
    if (snapshot.ai_settings && typeof snapshot.ai_settings === "object") this.saveAiSettings(snapshot.ai_settings);
    if (snapshot.tariff_settings && typeof snapshot.tariff_settings === "object") {
      await this.callService("deye_energy_manager", "save_tariff_settings", { data: JSON.stringify(snapshot.tariff_settings) });
    }
    for (const entityId of [chargeScheduler, scheduler]) {
      if (!entityId || !this.exists(entityId) || !(entityId in snapshot.values)) continue;
      await this.callService("switch", snapshot.values[entityId] === "on" ? "turn_on" : "turn_off", { entity_id: entityId });
    }
    if (controlMode && this.exists(controlMode) && controlMode in snapshot.values) {
      await this.callService("select", "select_option", { entity_id: controlMode, option: snapshot.values[controlMode] });
    }
    if (masterControl && this.exists(masterControl) && masterControl in snapshot.values) {
      await this.callService("switch", snapshot.values[masterControl] === "on" ? "turn_on" : "turn_off", { entity_id: masterControl });
    }

    const desiredControlOn = masterControl && this.exists(masterControl)
      ? (masterControl in snapshot.values ? snapshot.values[masterControl] === "on" : this.state(masterControl) === "on")
      : false;
    const physicalTou = Array.isArray(snapshot.physical_tou) ? snapshot.physical_tou : [];
    if (physicalTou.length && desiredControlOn && this.hasService("deye_energy_manager", "set_tou_slot")) {
      for (const row of physicalTou) {
        if (!row || row.slot < 1 || row.slot > 6 || row.soc === null) continue;
        await this.callService("deye_energy_manager", "set_tou_slot", {
          slot: Number(row.slot),
          start: String(row.start || "").slice(0, 5),
          end: String(row.end || "").slice(0, 5),
          soc: Number(row.soc),
          grid_charge: row.grid_charge === true,
        });
      }
    } else if (physicalTou.length && !desiredControlOn) {
      this._saveMessage = "Konfigurację lokalną przywrócono. Sterowanie Deye jest wyłączone — fizycznego TOU nie wysłano do falownika.";
    }
  }

  exportConfiguration() {
    const snapshot = this.configurationSnapshot();
    this.downloadHistory(`deye-konfiguracja-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(snapshot, null, 2), "application/json");
  }

  createConfigurationBackup() {
    const snapshot = this.configurationSnapshot();
    localStorage.setItem("deye_energy_manager_config_backup_v076", JSON.stringify(snapshot));
    this.downloadHistory(`deye-kopia-zapasowa-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(snapshot, null, 2), "application/json");
  }

  async restoreConfigurationBackup() {
    const raw = localStorage.getItem("deye_energy_manager_config_backup_v076") || localStorage.getItem("deye_energy_manager_config_backup_v074");
    if (!raw) throw new Error("Brak lokalnej kopii zapasowej");
    await this.applyConfigurationSnapshot(JSON.parse(raw));
  }

  refreshConfiguredEntities() {
    const entityIds = Object.keys(this._hass?.states || {}).filter((entityId) => entityId.includes("deye_energy_manager_") || entityId.startsWith("select.deye_inverter_") || entityId.startsWith("number.deye_inverter_") || entityId.startsWith("sensor.deye_inverter_"));
    if (entityIds.length) this.callService("homeassistant", "update_entity", { entity_id: entityIds });
  }

  renderDiagnostics(slots) {
    const entity = this._hass?.states?.[this.entity("sensor", "diagnostics")];
    const attrs = entity?.attributes || {};
    const required = Array.isArray(attrs.entities) ? attrs.entities : [];
    const entityRows = required.length ? required.map((item) => `<tr><td>${this.escapeHtml(item.entity_id)}</td><td><span class="diag-badge ${item.ok ? "ok" : "error"}">${item.ok ? "OK" : this.escapeHtml(item.state)}</span></td></tr>`).join("") : `<tr><td colspan="2">Brak danych diagnostycznych. Uruchom ponownie Home Assistant.</td></tr>`;
    const connected = attrs.connected === true;
    const mappingSegments = attrs.mapping_segments ?? this.scheduleSegments(slots).length;
    const tou = attrs.tou || {};
    const capabilities = attrs.capabilities && typeof attrs.capabilities === "object" ? attrs.capabilities : {};
    const provider = capabilities.provider && typeof capabilities.provider === "object" ? capabilities.provider : {};
    const missingTou = Array.isArray(tou.missing) ? tou.missing : [];
    const attempt = attrs.last_schedule_attempt && typeof attrs.last_schedule_attempt === "object" ? attrs.last_schedule_attempt : null;
    const activeControl = attrs.active_slot_control && typeof attrs.active_slot_control === "object" ? attrs.active_slot_control : {};
    const physicalTou = Array.isArray(attrs.physical_tou) ? attrs.physical_tou : [];
    const diagnosticValue = (value) => value === null || value === undefined || value === "" ? "brak" : String(value);
    const renderValues = (values) => Object.entries(values || {}).map(([label, value]) => `<li><span>${this.escapeHtml(label)}</span><strong>${this.escapeHtml(String(value))}</strong></li>`).join("") || "<li>Brak danych</li>";
    const attemptSection = attempt?.status ? `<section class="diagnostic-section"><h3>Ostatnia pr\u00f3ba zastosowania harmonogramu</h3><div class="schedule-attempt ${attempt.status === "failed" ? "failed" : "ok"}"><div><span>Wynik</span><strong>${attempt.status === "failed" ? "Nieudana" : attempt.status === "applied" ? "Potwierdzona" : "W toku"}</strong></div><div><span>Czas / slot</span><strong>${this.formatAppliedAt(attempt.at)} \u00b7 ${this.escapeHtml(attempt.slot || "brak")}</strong></div><div><span>Etap</span><strong>${this.escapeHtml(attempt.stage || "brak")}</strong></div><div class="schedule-attempt-message"><span>Szczeg\u00f3\u0142y</span><strong>${this.escapeHtml(attempt.message || "Brak dodatkowej informacji")}</strong></div><div><span>Oczekiwane</span><ul>${renderValues(attempt.expected)}</ul></div><div><span>Odczytane</span><ul>${renderValues(attempt.actual)}</ul></div></div></section>` : "";
    const currentRows = Object.entries(activeControl.currents || {}).map(([name, value]) => `<tr><td>${this.escapeHtml(name)}</td><td>${this.escapeHtml(diagnosticValue(value))}</td></tr>`).join("") || `<tr><td colspan="2">Brak danych o pr\u0105dach</td></tr>`;
    const activeControlSection = `<section class="diagnostic-section"><h3>SOC i parametry aktywnego slotu</h3><div class="schedule-attempt"><div><span>Slot / tryb</span><strong>${this.escapeHtml(diagnosticValue(activeControl.slot))} \u00b7 ${this.escapeHtml(diagnosticValue(activeControl.mode))}</strong></div><div><span>Próg zatrzymania sprzedaży</span><strong>${this.escapeHtml(diagnosticValue(activeControl.minimum_sell_soc))}%</strong></div><div><span>Fizyczny SOC Deye TOU</span><strong>${this.escapeHtml(diagnosticValue(activeControl.tou_soc))}%</strong></div><div><span>Docelowy SOC profilu Ładowania</span><strong>${this.escapeHtml(diagnosticValue(activeControl.charge_profile_target_soc))}%</strong></div><div><span>Efektywny SOC TOU</span><strong>${this.escapeHtml(diagnosticValue(activeControl.effective_tou_soc))}%</strong></div><div><span>Fizyczny zakres / odczyt SOC</span><strong>${this.escapeHtml(diagnosticValue(activeControl.physical_range))} \u00b7 ${this.escapeHtml(diagnosticValue(activeControl.physical_soc_actual))}%</strong></div><div><span>Grid Charge oczekiwany / odczytany</span><strong>${activeControl.grid_charge_expected ? "TAK" : "NIE"} \u00b7 ${this.escapeHtml(diagnosticValue(activeControl.grid_charge_actual))}</strong></div><div><span>Sprzedaż zablokowana przez SOC</span><strong>${activeControl.sale_blocked_by_soc ? "TAK" : "NIE"}</strong></div><div><span>Domyślny prąd rozładowania po zatrzymaniu sprzedaży</span><strong>${this.escapeHtml(diagnosticValue(activeControl.default_discharge_current_after_stop))} A</strong></div><div><span>Manager wymusza 0 A</span><strong>${activeControl.manager_does_not_force_zero_a ? "NIE" : "TAK"}</strong></div><div class="schedule-attempt-message"><span>Pr\u0105dy oczekiwane i odczytane</span><table class="settings-table"><tbody>${currentRows}</tbody></table></div></div></section>`;
    const powerLimits = activeControl.power_limits || {};
    const powerLimitsSection = `<section class="diagnostic-section"><h3>Ograniczenia mocy sprzeda\u017cy</h3><div class="schedule-attempt"><div><span>Moc docelowa / ograniczona</span><strong>${diagnosticValue(powerLimits.target_sell_power_w)} W / ${diagnosticValue(powerLimits.applied_sell_power_w)} W</strong></div><div><span>Skonfigurowany limit</span><strong>${diagnosticValue(powerLimits.configured_inverter_max_power_w)} W</strong></div><div><span>Wykryty limit encji</span><strong>${diagnosticValue(powerLimits.detected_entity_max_power_w)} W</strong></div><div><span>Efektywny limit</span><strong>${diagnosticValue(powerLimits.effective_inverter_max_power_w)} W</strong></div></div></section>`;
    const physicalRows = physicalTou.map((row) => `<tr class="${row.actual_active ? "active" : ""}"><td>${this.escapeHtml(diagnosticValue(row.range))}</td><td>${this.escapeHtml(diagnosticValue(row.expected_start))}\u2013${this.escapeHtml(diagnosticValue(row.expected_end))}</td><td>${this.escapeHtml(diagnosticValue(row.actual_start))}\u2013${this.escapeHtml(diagnosticValue(row.actual_end))}</td><td>${this.escapeHtml(diagnosticValue(row.expected_soc))}% / ${this.escapeHtml(diagnosticValue(row.actual_soc))}%</td><td>${row.expected_grid_charge ? "TAK" : "NIE"} / ${this.escapeHtml(this.touGridLabel(row.actual_grid_charge))}</td></tr>`).join("") || `<tr><td colspan="5">Brak danych fizycznego mapowania</td></tr>`;
    const physicalSection = tou.supported === false ? "" : `<section class="diagnostic-section"><h3>Fizyczne zakresy Deye TOU</h3><div class="diagnostic-entities"><table class="settings-table"><thead><tr><th>Zakres</th><th>Oczekiwane godziny</th><th>Odczytane godziny</th><th>SOC oczekiwany / odczytany</th><th>Grid oczekiwany / odczytany</th></tr></thead><tbody>${physicalRows}</tbody></table></div></section>`;
    const touState = tou.supported === false ? "OGRANICZONE" : tou.ok === false ? "B\u0141\u0104D" : "OK";
    const touMessage = tou.supported === false
      ? (tou.note || "Wybrany dostawca nie udost\u0119pnia bezpiecznego sterowania Time Of Use w Home Assistant.")
      : tou.ok === false
        ? `Brakuje encji: ${missingTou.join(", ")}`
        : "Wszystkie encje Time Of Use s\u0105 dost\u0119pne";
    const touSection = `<section class="diagnostic-section"><h3>Mapowanie Deye Time Of Use</h3><div class="tou-diagnostics"><span class="diag-badge ${tou.supported === false ? "" : tou.ok === false ? "error" : "ok"}">${touState}</span><strong>${this.escapeHtml(touMessage)}</strong></div></section>`;
    const capabilityLabels = {
      readings: "Odczyty podstawowe",
      basic_control: "Sterowanie podstawowe",
      selling: "Sprzeda\u017c",
      charging: "\u0141adowanie",
      full_tou: "Pe\u0142ne Deye Time Of Use",
      core_ai: "Komplet danych Core / AI",
    };
    const capabilityRows = Object.entries(capabilityLabels).map(([key, label]) => {
      const item = capabilities[key] || {};
      const text = item.supported === false ? "NIEOBS\u0141UGIWANE" : item.ok ? "OK" : `BRAKI: ${(item.missing || []).join(", ") || "brak danych"}`;
      return `<tr><td>${label}</td><td><span class="diag-badge ${item.ok ? "ok" : item.supported === false ? "" : "error"}">${this.escapeHtml(text)}</span></td></tr>`;
    }).join("");
    const operationRows = Object.entries(capabilities.operations || {}).filter(([_key, item]) => item?.entity_id && item.entity_id !== "not_configured").map(([key, item]) => `<tr><td>${this.escapeHtml(key)}</td><td>${this.escapeHtml(item.entity_id)}</td><td>${this.escapeHtml(item.operation)}</td></tr>`).join("");
    const capabilitySection = `<section class="diagnostic-section"><h3>Mo\u017cliwo\u015bci po\u0142\u0105czenia z falownikiem</h3><div class="tou-diagnostics"><strong>${this.escapeHtml(provider.label || attrs.inverter_provider_label || "Nieznany profil")}</strong><span>${this.escapeHtml(provider.note || "Zakres funkcji wynika z dost\u0119pnych encji Home Assistant.")}</span></div><div class="diagnostic-entities"><table class="settings-table"><tbody>${capabilityRows}</tbody></table></div>${operationRows ? `<details><summary>Operacje przypisane do encji</summary><div class="diagnostic-entities"><table class="settings-table"><thead><tr><th>Funkcja</th><th>Encja</th><th>Operacja HA</th></tr></thead><tbody>${operationRows}</tbody></table></div></details>` : ""}</section>`;
    return `<div class="diagnostic-summary">
      <div><span>Po\u0142\u0105czenie z falownikiem</span><strong class="${connected ? "good" : "bad"}">${connected ? "Po\u0142\u0105czono" : "Problem"}</strong></div>
      <div><span>Stan managera</span><strong class="${this.readMode(attrs.manager_status || "NO DATA")[1]}">${this.readMode(attrs.manager_status || "NO DATA")[0]}</strong></div>
      <div><span>Slot harmonogramu</span><strong>${attrs.active_slot || "brak"} \u00b7 nast\u0119pny ${attrs.next_active_slot || "brak"}</strong></div>
      <div><span>Harmonogram i mapowanie</span><strong class="${attrs.mapping_status === "OK" ? "good" : "bad"}">${attrs.mapping_status || "brak"} \u00b7 ${mappingSegments}/6</strong></div>
      <div><span>Ostatni zapis</span><strong>${this.formatAppliedAt(attrs.last_saved_at)}</strong></div>
      <div><span>Ostatnie zastosowanie</span><strong>${this.formatAppliedAt(attrs.last_applied_at)}</strong></div>
      <div><span>Ostatni b\u0142\u0105d</span><strong class="${attrs.last_error && attrs.last_error !== "none" ? "bad" : "good"}">${attrs.last_error && attrs.last_error !== "none" ? this.escapeHtml(attrs.last_error) : "Brak"}</strong></div>
      <div><span>Wersje</span><strong>Integracja ${this.escapeHtml(attrs.integration_version || "0.8.0")} \u00b7 karta 0.8.0 (rewizja zasobu v=0.8.0.44)</strong></div>
    </div>
    ${attemptSection}
    ${capabilitySection}
    ${activeControlSection}
    ${powerLimitsSection}
    ${physicalSection}
    ${touSection}
    <section class="diagnostic-section"><h3>Wymagane encje</h3><div class="diagnostic-entities"><table class="settings-table"><thead><tr><th>Encja</th><th>Stan</th></tr></thead><tbody>${entityRows}</tbody></table></div></section>
    <section class="diagnostic-section"><h3>Sterowanie i odczyt</h3><div class="diagnostic-actions"><button class="resume" data-resume-manager="1" ${this._resumeApplying ? "disabled" : ""}>${this._resumeApplying ? "W\u0142\u0105czanie Managera\u2026" : "W\u0142\u0105cz Manager i harmonogram"}</button><button data-system-defaults="1" data-default-action="1" data-default-label="Zatrzymaj managera i zastosuj domy\u015blne" ${this._defaultsApplying ? "disabled" : ""}>${this._defaultsApplying ? "Stosowanie ustawie\u0144 domy\u015blnych\u2026" : "Zatrzymaj managera i zastosuj domy\u015blne"}</button><button data-refresh-entities="1">Ponownie odczytaj encje</button></div><p class="hint">W\u0142\u0105czenie Managera ustawia tryb Schedule i Scheduler. Nie w\u0142\u0105cza oddzielnego harmonogramu \u0142adowania z sieci.</p></section>
    <section class="diagnostic-section"><h3>Konfiguracja i kopia zapasowa</h3><div class="diagnostic-actions"><button data-export-config="1">Eksport konfiguracji</button><button data-import-config-open="1">Import konfiguracji</button><input type="file" accept="application/json,.json" data-import-config hidden><button data-create-backup="1">Utw\u00f3rz kopi\u0119 zapasow\u0105</button><button data-restore-backup="1">Przywr\u00f3\u0107 kopi\u0119</button><button class="danger" data-restore-defaults="1" data-default-action="1" data-default-label="Przywr\u00f3\u0107 ustawienia domy\u015blne" ${this._defaultsApplying ? "disabled" : ""}>${this._defaultsApplying ? "Stosowanie ustawie\u0144 domy\u015blnych\u2026" : "Przywr\u00f3\u0107 ustawienia domy\u015blne"}</button></div><div class="hint defaults-status ${this._defaultsStatus}" data-defaults-status ${this._defaultsMessage ? "" : "hidden"}>${this.escapeHtml(this._defaultsMessage)}</div></section>`;
  }

  aiCheck(name, label, value) {
    return `<div class="settings-row"><span>${label}</span><input data-ai-setting="${name}" type="checkbox" ${value ? "checked" : ""}></div>`;
  }

  tariffData() {
    const tariffState = this._hass?.states?.[this.entity("sensor", "tariff_status")];
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    return tariffState?.attributes || aiState?.attributes?.learning_summary?.tariff || aiState?.attributes?.tariff || {};
  }

  canonicalPriceData(planner = null) {
    if (planner?.canonical_prices?.schema_version === 1) return planner.canonical_prices;
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const backend = aiState?.attributes?.planner_48h?.canonical_prices;
    return backend?.schema_version === 1 ? backend : { schema_version: 1, buy: { rows: [] }, sell: { rows: [] } };
  }

  canonicalPriceRows(direction, planner = null) {
    const branch = this.canonicalPriceData(planner)?.[direction];
    return Array.isArray(branch?.rows)
      ? branch.rows.filter((row) => row && row.quality === "ready")
      : [];
  }

  canonicalPriceMaps(direction, field = "final_price_pln_kwh", planner = null) {
    const maps = [new Map(), new Map()];
    this.canonicalPriceRows(direction, planner).forEach((row) => {
      const day = row.day === "today" ? 0 : row.day === "tomorrow" ? 1 : -1;
      const hour = Number(row.hour);
      const value = this.asNumber(row[field]);
      if (day >= 0 && Number.isInteger(hour) && hour >= 0 && hour < 24 && value !== null) maps[day].set(hour, value);
    });
    return maps;
  }

  tariffZoneLabel(zone) {
    return {
      all_day: "Całodobowa", peak: "Szczytowa", offpeak: "Tania / pozaszczytowa",
      morning_peak: "Szczyt przedpołudniowy", afternoon_peak: "Szczyt popołudniowy",
      day_peak: "Dzienna szczytowa", day_offpeak: "Dzienna pozaszczytowa", night: "Nocna",
      recommended: "Zalecany pobór", restriction: "Zalecane ograniczenie", normal: "Pozostałe godziny",
      other: "Pozostałe godziny", dynamic_unavailable: "Brak sygnału dynamicznego",
    }[zone] || String(zone || "brak");
  }

  localDateKey(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  collectTariffDraft() {
    const draft = { ...(this._tariffDraft || {}) };
    this.querySelectorAll("[data-tariff-field]").forEach((el) => {
      const key = el.dataset.tariffField;
      if (el.type === "checkbox") draft[key] = el.checked;
      else if (["distribution_peak_rate", "distribution_offpeak_rate"].includes(key)) draft[key] = this.asNumber(el.value) ?? el.value;
      else draft[key] = el.value;
    });
    this.querySelectorAll("[data-price-contract]").forEach((el) => {
      const direction = el.dataset.priceContract;
      const key = el.dataset.contractField;
      const targetKey = `${direction}_price_contract`;
      const contract = { ...(draft[targetKey] || {}) };
      let value = el.type === "checkbox" ? el.checked : el.value;
      if (["includes_distribution_variable", "includes_excise", "includes_service_margin"].includes(key)) {
        value = value === "true" ? true : value === "false" ? false : null;
      } else if (key === "vat_rate") {
        value = value === "" ? null : (this.asNumber(value) ?? value);
      }
      contract[key] = value;
      draft[targetKey] = contract;
    });
    if (draft.osd_provider) {
      draft.tariff_mode = draft.osd_provider === "other" || draft.tariff_plan === "custom"
        ? "manual"
        : "automatic";
    }
    this._tariffDraft = draft;
    return draft;
  }

  renderPriceMappingSummary(tariff) {
    const roleLabel = (role) => ({
      retail_buy_all_in: "detaliczna BUY all-in",
      energy_only: "tylko energia",
      market_reference: "referencyjna rynkowa",
      prosumer_sell: "sprzedaż prosumencka",
      custom: "własna",
    }[role] || "rola nieustalona");
    const statusLabel = (value, entity) => !entity
      ? "nie skonfigurowano"
      : ({ bound: "powiązano", entity_id_only: "mapowanie zapisane", mapped_entity_missing: "encja niedostępna" }[value] || value || "oczekuje na dane");
    const rows = [];
    for (const direction of ["buy", "sell"]) {
      const contract = tariff.price_contracts?.[direction] || {};
      for (const day of ["today", "tomorrow"]) {
        const entity = contract[`${day}_entity`] || "";
        const profile = contract[`resolved_source_${day}`] || contract;
        const adapter = contract[`resolved_adapter_${day}`] || "unmapped";
        const status = contract[`stable_identity_${day}_status`] || "";
        rows.push(`<div class="price-mapping-summary-row"><span>${direction.toUpperCase()} ${day === "today" ? "Today" : "Tomorrow"}</span><strong>${this.escapeHtml(entity || "brak")}</strong><small>${this.escapeHtml(statusLabel(status, entity))} · ${this.escapeHtml(adapter)} · ${this.escapeHtml(roleLabel(profile.economic_role))}</small></div>`);
      }
    }
    const buy = tariff.price_contracts?.buy || {};
    const buyProfiles = [buy.resolved_source_today || buy, buy.resolved_source_tomorrow || buy];
    const osdIncluded = buyProfiles.some((profile) => profile.economic_role === "retail_buy_all_in" || profile.includes_distribution_variable === true);
    const detected = [tariff.price_contracts?.buy?.adapter_summary, tariff.price_contracts?.sell?.adapter_summary]
      .filter((value) => value && value !== "unmapped").join(" / ") || "brak";
    return `<section class="diagnostic-section price-mapping-summary"><h3>Źródła cen</h3><p><strong>Wykryte źródło: ${this.escapeHtml(detected)}</strong> · ${osdIncluded ? "OSD zawarte" : "OSD doliczane zgodnie z taryfą"}</p><div class="diagnostic-summary">${rows.join("")}</div><p class="hint">Encje cen BUY/SELL konfiguruje się w ustawieniach integracji.</p></section>`;
  }

  renderPriceContract(direction, contract = {}) {
    const label = direction === "buy" ? "BUY — zakup" : "SELL — sprzedaż";
    const dayAdapters = [contract.resolved_adapter_today, contract.resolved_adapter_tomorrow].filter((value) => value && value !== "unmapped");
    const known = dayAdapters.some((value) => ["pstryk", "rce_pse"].includes(value));
    const unmapped = !contract.today_entity && !contract.tomorrow_entity;
    const adapterLabel = contract.adapter_summary || contract.source_adapter || (unmapped ? "unmapped" : "generic");
    const mappingSummary = `<div class="diagnostic-summary"><div><span>Today — mapowanie nadrzędne</span><strong>${this.escapeHtml(contract.today_entity || "brak")}</strong></div><div><span>Tomorrow — mapowanie nadrzędne</span><strong>${this.escapeHtml(contract.tomorrow_entity || "brak")}</strong></div><div><span>Adapter</span><strong>${this.escapeHtml(adapterLabel)}</strong></div><div><span>Źródło metadanych</span><strong>automatycznie z mapowania</strong></div></div>`;
    const yesNo = (value) => value === true ? "tak" : value === false ? "nie" : "brak";
    const readOnlyDay = (day, title) => {
      const adapter = contract[`resolved_adapter_${day}`] || "unmapped";
      if (adapter === "unmapped") return `<div><span>${title}</span><strong>nie skonfigurowano</strong></div>`;
      const profile = contract[`resolved_source_${day}`] || contract;
      const schema = contract[`resolved_schema_${day}`] || {};
      return `<div><span>${title}</span><strong>${this.escapeHtml(adapter)} · ${this.escapeHtml(schema.schema_id || "schema oczekuje na dane")}</strong><small>${this.escapeHtml(profile.economic_role || "brak roli")} · ${this.escapeHtml(profile.semantic_scope || "brak semantyki")} · dystrybucja ${yesNo(profile.includes_distribution_variable)} · akcyza ${yesNo(profile.includes_excise)} · marża/usługa ${yesNo(profile.includes_service_margin)}</small></div>`;
    };
    const field = (name, title, values = null) => {
      const value = contract[name] ?? "";
      const control = values
        ? `<select data-price-contract="${direction}" data-contract-field="${name}">${values.map(([key, text]) => `<option value="${this.escapeHtml(key)}" ${String(value) === String(key) ? "selected" : ""}>${this.escapeHtml(text)}</option>`).join("")}</select>`
        : `<input data-price-contract="${direction}" data-contract-field="${name}" type="text" value="${this.escapeHtml(value)}">`;
      return `<div class="settings-row"><span>${title}</span>${control}</div>`;
    };
    const tri = [["unknown", "nieznane — fail closed"], ["true", "tak"], ["false", "nie"]];
    if (known || unmapped) {
      return `<details class="diagnostic-section"><summary><b>${label}</b> · ${this.escapeHtml(adapterLabel)} · automatyczne / tylko odczyt</summary>
        ${mappingSummary}
        <div class="diagnostic-summary readonly-price-contract">${readOnlyDay("today", "Today — kontrakt automatyczny")}${readOnlyDay("tomorrow", "Tomorrow — kontrakt automatyczny")}</div>
        <p class="hint">Encje zmienia się wyłącznie w kroku „Encje cen energii”. Adapter, schema i semantyka znanych integracji są rozpoznawane od nowa po zmianie mapowania.</p>
      </details>`;
    }
    return `<details class="diagnostic-section custom-price-contract"><summary><b>${label}</b> · ${this.escapeHtml(adapterLabel)} · Zaawansowane / Custom — ustawienia własnego źródła</summary>
      ${mappingSummary}
      ${field("source_adapter", "Tryb kontraktu", [["generic", "Ogólny — fail closed"], ["custom", "Własny kontrakt"]])}
      ${field("economic_role", "Rola ekonomiczna", [["", "wybierz — fail closed"], ["retail_buy_all_in", "detaliczna BUY all-in"], ["energy_only", "tylko energia"], ["market_reference", "referencyjna rynkowa"], ["prosumer_sell", "sprzedaż prosumencka"], ["custom", "własna"]])}
      ${field("semantic_scope", "Znaczenie ceny", [["energy_only", "tylko energia"], ["all_in_variable", "pełna zmienna"], ["partial", "częściowa / niejednoznaczna"]])}
      ${field("price_basis", "Podstawa", [["gross", "brutto"], ["net", "netto"], ["unknown", "nieznana — fail closed"]])}
      ${field("unit", "Jednostka", [["PLN/kWh", "PLN/kWh"], ["PLN/MWh", "PLN/MWh"], ["unknown", "nieznana — fail closed"]])}
      ${field("includes_distribution_variable", "Zawiera zmienną dystrybucję", tri)}
      ${field("includes_excise", "Zawiera akcyzę", tri)}
      ${field("includes_service_margin", "Zawiera marżę/usługę", tri)}
      ${field("list_attribute", "Atrybut listy")}${field("today_list_attribute", "Atrybut listy Today")}${field("tomorrow_list_attribute", "Atrybut listy Tomorrow")}
      ${field("value_field", "Pole wartości")}${field("start_field", "Pole początku")}${field("end_field", "Pole końca")}
      ${field("period_field", "Pole okresu")}${field("timestamp_field", "Pole czasu")}
      ${field("timestamp_role", "Znaczenie czasu", [["start", "początek"], ["end", "koniec"]])}
      ${field("business_date_field", "Pole dnia handlowego")}
      ${field("granularity", "Rozdzielczość", [["15m", "15 min"], ["60m", "60 min"], ["timestamp_series", "seria znaczników"], ["unknown", "nieznana"]])}
      ${field("vat_rate", "VAT jako ułamek (np. 0.23)")}
    </details>`;
  }

  renderPriceDiagnostics(tariff) {
    const snapshot = tariff.price_diagnostics || {};
    const resolverLabel = (value) => ({
      unmapped: "nie skonfigurowano",
      user_unmapped: "usunięto w mapowaniu",
      mapped_entity_missing: "brak mapowanej encji",
      unsupported_price_schema: "nieobsługiwany schema cen",
      incomplete_price_series: "niepełna seria cen",
      price_source_not_configured: "źródło cen nie skonfigurowane",
    }[value] || value || "brak");
    const line = (direction) => {
      const hasAuthoritative = Boolean(tariff.price_contracts && Object.prototype.hasOwnProperty.call(tariff.price_contracts, direction));
      const authoritative = tariff.price_contracts?.[direction] || {};
      const branch = snapshot[direction] || {};
      const sellerCatalog = branch.contract?.source_adapter === "seller_catalog";
      const unmapped = hasAuthoritative && !authoritative.today_entity && !authoritative.tomorrow_entity && !sellerCatalog;
      const contract = unmapped ? authoritative : branch.contract || authoritative;
      const diag = unmapped ? { status: "price_source_not_configured", coverage_today: 0, coverage_tomorrow: 0 } : branch.diagnostics || {};
      const rows = unmapped ? [] : Array.isArray(branch.rows) ? branch.rows : [];
      const now = rows.find((row) => row.day === "today" && Number(row.hour) === (this.localDateTimeParts()?.hour ?? new Date().getHours()));
      const addedOsd = rows.some((row) => Math.abs(this.asNumber(row.added_distribution) || 0) > 1e-12);
      const aggregation = contract.granularity === "15m" ? "15m→60m ważona" : `${contract.granularity || "per-day"}→60m`;
      return `<tr><td>${direction.toUpperCase()}</td><td>${this.escapeHtml(contract.adapter_summary || contract.source_adapter || "brak")}</td><td>${this.escapeHtml(contract.economic_role || "brak roli")} / ${this.escapeHtml(contract.semantic_scope || "per-day")}</td><td>${this.escapeHtml(contract.unit || "per-day")} / ${this.escapeHtml(contract.price_basis || "per-day")}</td><td>${this.escapeHtml(aggregation)}</td><td>${diag.coverage_today || 0}/24 · ${diag.coverage_tomorrow || 0}/24</td><td>${addedOsd ? "tak" : "nie"}</td><td>${this.escapeHtml(resolverLabel(diag.status || "waiting_data"))}</td><td>${now ? `${this.formatPrice(now.final_price_pln_kwh)} PLN/kWh` : "brak"}</td></tr>`;
    };
    const resolverLine = (direction, day) => {
      const hasAuthoritative = Boolean(tariff.price_contracts && Object.prototype.hasOwnProperty.call(tariff.price_contracts, direction));
      const authoritative = tariff.price_contracts?.[direction] || {};
      const mapped = hasAuthoritative ? authoritative[`${day}_entity`] || "" : null;
      const branch = snapshot[direction] || {};
      const sellerCatalog = branch.contract?.source_adapter === "seller_catalog";
      const resolver = mapped === "" && !sellerCatalog ? {
        mapped_entity: "", resolved_entity: "", stable_identity_status: "unmapped",
        detected_adapter: "unmapped", resolved_schema: "brak", coverage_hours: 0,
        status: "unmapped", reason: "user_unmapped",
      } : branch.diagnostics?.resolver?.[day] || {};
      const schema = resolver.resolved_schema || "unknown";
      return `<tr><td>${direction.toUpperCase()} ${day === "today" ? "Today" : "Tomorrow"}</td><td>${this.escapeHtml(resolver.mapped_entity || "brak")}</td><td>${this.escapeHtml(resolver.resolved_entity || "brak")}</td><td>${this.escapeHtml(resolverLabel(resolver.stable_identity_status || "unbound"))}</td><td>${this.escapeHtml(resolver.detected_adapter || "generic")}</td><td>${this.escapeHtml(typeof schema === "string" ? schema : schema.schema_id || "unknown")}</td><td>${this.escapeHtml(resolver.list_attribute || "brak")} / ${this.escapeHtml(resolver.value_field || "brak")}</td><td>${this.escapeHtml(resolver.unit || "unknown")} / ${this.escapeHtml(resolver.economic_role || "brak roli")} / ${this.escapeHtml(resolver.semantic_scope || "unknown")}</td><td>${Number(resolver.coverage_hours || 0)}/24</td><td>${this.escapeHtml(resolverLabel(resolver.status || "waiting_data"))}${resolver.reason ? ` · ${this.escapeHtml(resolverLabel(resolver.reason))}` : ""}</td></tr>`;
    };
    return `<details class="diagnostic-section tariff-price-diagnostics"><summary><b>Diagnostyka techniczna cen</b> · resolver, schema i pokrycie</summary><section><h3>Kanoniczne ceny backendu</h3><div class="diagnostic-entities"><table class="settings-table"><thead><tr><th>Kierunek</th><th>Źródło</th><th>Typ ceny</th><th>Jednostka / netto-brutto</th><th>Agregacja</th><th>Pokrycie</th><th>DEM dodał OSD</th><th>Status</th><th>Cena końcowa Core</th></tr></thead><tbody>${line("buy")}${line("sell")}</tbody></table></div><h4>Resolver mapowanych encji</h4><div class="diagnostic-entities"><table class="settings-table"><thead><tr><th>Mapowanie</th><th>Wybrana encja</th><th>Rozwiązana encja</th><th>Stable identity</th><th>Adapter</th><th>Schema</th><th>Lista / wartość</th><th>Jednostka / semantyka</th><th>Pokrycie</th><th>Status / powód</th></tr></thead><tbody>${resolverLine("buy", "today")}${resolverLine("buy", "tomorrow")}${resolverLine("sell", "today")}${resolverLine("sell", "tomorrow")}</tbody></table></div><p class="hint">Nieznana jednostka, podstawa, rola lub semantyka blokuje planowanie (fail closed). Dystrybucja, VAT i inne składniki są dodawane wyłącznie w backendzie. Frontend nie odczytuje ani nie zgaduje schematu encji źródłowych.</p></section></details>`;
  }

  async saveTariffSettings() {
    const button = this.querySelector("[data-save-tariff]");
    if (button) button.disabled = true;
    try {
      const data = this.collectTariffDraft();
      await this.callService("deye_energy_manager", "save_tariff_settings", { data: JSON.stringify(data) });
      this._tariffDraft = null;
      this._tariffSaveStatus = "Zapisano. Profil i sugestie AI korzystają z nowych ustawień.";
    } catch (error) {
      this._tariffSaveStatus = `Błąd zapisu: ${error?.message || error}`;
    }
    this.render();
  }

  renderTariffTab() {
    const tariff = this.tariffData();
    const draft = {
      tariff_mode: tariff.mode || "automatic",
      osd_provider: tariff.provider || "pge",
      tariff_plan: tariff.plan || "g11",
      price_includes_distribution: Boolean(tariff.price_includes_distribution),
      buy_price_contract: { ...(tariff.price_contracts?.buy || {}) },
      sell_price_contract: { ...(tariff.price_contracts?.sell || {}) },
      distribution_peak_rate: tariff.peak_rate ?? 0,
      distribution_offpeak_rate: tariff.offpeak_rate ?? 0,
      custom_offpeak_windows: tariff.custom_offpeak_windows || "13:00-15:00,22:00-06:00",
      grid_positive_is_import: tariff.grid_positive_is_import !== false,
      battery_positive_is_discharge: tariff.battery_positive_is_discharge !== false,
      buy_seller_id: tariff.seller_fallback?.selected_seller_id || "",
      buy_seller_tariff_id: tariff.seller_fallback?.selected_seller_tariff_id || "",
      ...(this._tariffDraft || {}),
    };
    const providers = Array.isArray(tariff.providers) ? tariff.providers : [];
    const selectedProvider = providers.find((item) => item.id === draft.osd_provider);
    const tariffs = selectedProvider?.tariffs || (Array.isArray(tariff.tariffs) ? tariff.tariffs : []);
    if (tariffs.length && !tariffs.some((item) => item.id === draft.tariff_plan)) draft.tariff_plan = tariffs[0].id;
    const options = (rows, selected) => rows.map((item) => {
      const reason = item.available === false && item.unavailable_reason ? ` — ${item.unavailable_reason}` : "";
      const disabled = item.available === false && item.id !== selected ? "disabled" : "";
      return `<option value="${this.escapeHtml(item.id)}" ${item.id === selected ? "selected" : ""} ${disabled}>${this.escapeHtml(`${item.name}${reason}`)}</option>`;
    }).join("");
    const rows = Array.isArray(tariff.hourly_profile) ? tariff.hourly_profile : [];
    const profileRows = rows.map((row) => `<tr>
      <td>${this.escapeHtml(row.date || "")}</td><td>${this.escapeHtml(row.label || this.hourLabel(Number(row.hour)))}</td>
      <td>${this.escapeHtml(this.tariffZoneLabel(row.zone))}</td><td>${this.formatNumber(row.rate, 4)}</td>
      <td>${this.formatNumber(row.common_rate, 4)}</td><td>${this.formatNumber(row.total_distribution_rate ?? row.rate, 4)}</td>
      <td>${row.holiday ? "święto" : row.weekend ? "weekend" : "dzień roboczy"}</td>
    </tr>`).join("");
    const statusClass = tariff.catalog_error ? "bad" : tariff.configured ? "good" : "warn";
    const manual = draft.osd_provider === "other" || draft.tariff_plan === "custom";
    draft.tariff_mode = manual ? "manual" : "automatic";
    const isCustom = (contract) => {
      const mapped = Boolean(contract?.today_entity || contract?.tomorrow_entity);
      return mapped && (
        ["custom", "generic"].includes(contract?.source_adapter)
        || ["today", "tomorrow"].some((day) => ["custom", "generic"].includes(contract?.[`resolved_adapter_${day}`]))
      );
    };
    const buyMapped = Boolean(draft.buy_price_contract?.today_entity || draft.buy_price_contract?.tomorrow_entity);
    const fallback = tariff.seller_fallback || {};
    const support = fallback.support_matrix?.[draft.osd_provider]?.[draft.tariff_plan] || {};
    const sellerOptions = Array.isArray(fallback.seller_options) ? fallback.seller_options : [];
    const sellerName = (id) => sellerOptions.find((item) => item.id === id)?.name || id || "brak";
    const scopeKey = `${draft.osd_provider}/${draft.tariff_plan}/${draft.buy_seller_id || ""}`;
    const sellerTariffs = Array.isArray(fallback.tariff_options_by_scope?.[scopeKey])
      ? fallback.tariff_options_by_scope[scopeKey]
      : [];
    if (draft.buy_seller_tariff_id && !sellerTariffs.some((item) => item.id === draft.buy_seller_tariff_id)) {
      draft.buy_seller_tariff_id = "";
    }
    const sellerChoices = `<option value="">— wybierz —</option>${options(sellerOptions, draft.buy_seller_id)}`;
    const suggestedSeller = support.suggested_seller_id || fallback.suggested_seller_id || "";
    const unsupportedReason = draft.buy_seller_id && draft.buy_seller_id !== suggestedSeller
      ? "Brak zweryfikowanej standardowej taryfy tego sprzedawcy dla wybranej taryfy OSD."
      : support.reason || fallback.support_reason || "Brak ważnej, jednoznacznej taryfy standardowej.";
    const sellerFallbackUi = buyMapped ? "" : `<div class="seller-buy-fallback">
      <h4>Standardowy zakup energii</h4>
      <div class="settings-row"><span>Sprzedawca energii (zakup)</span><select data-tariff-field="buy_seller_id">${sellerChoices}</select></div>
      ${!draft.buy_seller_id && suggestedSeller ? `<p class="hint">Sugestia dla tego OSD: <b>${this.escapeHtml(sellerName(suggestedSeller))}</b>. Wybór nie jest wykonywany automatycznie.</p>` : ""}
      ${draft.buy_seller_id && sellerTariffs.length === 1 ? `<p class="hint good">Dopasowana taryfa sprzedawcy: <b>${this.escapeHtml(sellerTariffs[0].name)}</b>.</p>` : ""}
      ${draft.buy_seller_id && sellerTariffs.length > 1 ? `<div class="settings-row"><span>Taryfa sprzedawcy</span><select data-tariff-field="buy_seller_tariff_id"><option value="">— wybierz —</option>${options(sellerTariffs, draft.buy_seller_tariff_id)}</select></div>` : ""}
      ${draft.buy_seller_id && sellerTariffs.length === 0 ? `<p class="hint bad">Brak standardowego BUY: ${this.escapeHtml(unsupportedReason)} System pozostaje fail-closed.</p>` : ""}
    </div>`;
    const catalogValidity = tariff.catalog_current_validity === "valid" ? "ważny" : tariff.catalog_current_validity || "brak danych";
    return `<div class="hint">Operator, taryfa i stawki są zapisywane dopiero przyciskiem <b>Zapisz ustawienia</b>. Profil obejmuje dziś i jutro; weekendy, święta i sezony są wyliczane automatycznie.</div>
      <div class="diagnostic-summary"><div><span>Operator OSD</span><strong>${this.escapeHtml(tariff.provider_name || "brak")}</strong></div><div><span>Taryfa / sezon</span><strong>${this.escapeHtml(tariff.plan_name || "brak")} · ${tariff.season === "summer" ? "lato" : tariff.season === "winter" ? "zima" : "brak"}</strong></div><div><span>Bieżąca strefa</span><strong>${this.escapeHtml(this.tariffZoneLabel(tariff.zone))} · ${this.formatNumber(tariff.total_distribution_rate ?? tariff.distribution_rate, 4)} PLN/kWh</strong></div><div><span>Katalog</span><strong class="${statusClass}">${this.escapeHtml(tariff.catalog_version || "wbudowany")} · ${this.escapeHtml(tariff.catalog_source || "brak")}</strong></div></div>
      <section class="diagnostic-section"><h3>Ustawienia operatora i taryfy</h3>
        <div class="settings-row"><span>Operator OSD</span><select data-tariff-field="osd_provider">${options(providers, draft.osd_provider)}</select></div>
        <div class="settings-row"><span>Taryfa</span><select data-tariff-field="tariff_plan">${options(tariffs, draft.tariff_plan)}</select></div>
        ${manual ? `<div class="manual-osd-profile"><h4>Profil ręczny OSD</h4><div class="settings-row"><span>Stawka szczytowa [PLN/kWh]</span><input data-tariff-field="distribution_peak_rate" type="text" inputmode="decimal" value="${this.escapeHtml(draft.distribution_peak_rate)}"></div><div class="settings-row"><span>Stawka tania [PLN/kWh]</span><input data-tariff-field="distribution_offpeak_rate" type="text" inputmode="decimal" value="${this.escapeHtml(draft.distribution_offpeak_rate)}"></div><div class="settings-row"><span>Własne tanie godziny</span><input data-tariff-field="custom_offpeak_windows" type="text" value="${this.escapeHtml(draft.custom_offpeak_windows)}"></div></div>` : ""}
        ${sellerFallbackUi}
        <div class="diagnostic-actions"><button class="wide-action" data-save-tariff="1">Zapisz ustawienia</button><button data-refresh-tariff="1">Sprawdź aktualizację katalogu</button></div>
        <p class="hint">Katalog lokalny: <b>${this.escapeHtml(tariff.catalog_local_version || tariff.catalog_version || "brak")}</b> · zdalny: <b>${this.escapeHtml(tariff.catalog_remote_version || "nie sprawdzono")}</b> · sprawdzono: <b>${this.escapeHtml(tariff.catalog_last_checked || "nigdy")}</b> · wynik: <b>${this.escapeHtml(tariff.catalog_update_result || "nie sprawdzono")}</b> · ważność: <b>${this.escapeHtml(catalogValidity)} (${this.escapeHtml(tariff.catalog_effective_from || "?")}–${this.escapeHtml(tariff.catalog_valid_to || "?")})</b></p>
        ${this._tariffSaveStatus ? `<div class="hint">${this.escapeHtml(this._tariffSaveStatus)}</div>` : ""}
        ${tariff.catalog_error ? `<div class="hint bad">${this.escapeHtml(tariff.catalog_error)}. Używany jest ostatni poprawny katalog.</div>` : ""}
        ${tariff.tariff_error ? `<div class="hint bad">Wybrany profil nie jest dostępny: ${this.escapeHtml(tariff.tariff_error)}. AI nie użyje go do planowania ładowania.</div>` : ""}
      </section>
      ${this.renderPriceMappingSummary(tariff)}
      ${isCustom(draft.buy_price_contract) ? this.renderPriceContract("buy", draft.buy_price_contract) : ""}
      ${isCustom(draft.sell_price_contract) ? this.renderPriceContract("sell", draft.sell_price_contract) : ""}
      <details class="diagnostic-section tariff-advanced"><summary><b>Zaawansowane</b> · polaryzacja przepływów</summary><div class="settings-row"><span>Dodatnia moc sieci oznacza pobór</span><input data-tariff-field="grid_positive_is_import" type="checkbox" ${draft.grid_positive_is_import ? "checked" : ""}></div><div class="settings-row"><span>Dodatnia moc baterii oznacza rozładowanie</span><input data-tariff-field="battery_positive_is_discharge" type="checkbox" ${draft.battery_positive_is_discharge ? "checked" : ""}></div></details>
      ${this.renderPriceDiagnostics(tariff)}
      <section class="diagnostic-section"><h3>Profil kosztu dystrybucji — dziś i jutro</h3><div class="diagnostic-entities"><table class="settings-table"><thead><tr><th>Data</th><th>Godzina</th><th>Strefa</th><th>Sieciowa</th><th>Opłaty zmienne</th><th>Razem</th><th>Rodzaj dnia</th></tr></thead><tbody>${profileRows || '<tr><td colspan="7">Brak profilu. Wybierz operatora i taryfę, a następnie zapisz.</td></tr>'}</tbody></table></div></section>`;
  }

  aiNumber(name, label, value, unit = "") {
    return `<div class="settings-row"><span>${label}</span><label class="field compact-field"><input data-ai-setting="${this.escapeHtml(name)}" type="text" inputmode="decimal" value="${this.escapeHtml(value)}"><span>${this.escapeHtml(unit)}</span></label></div>`;
  }

  aiSelect(name, label, options, value) {
    return `<div class="settings-row"><span>${label}</span><select data-ai-setting="${name}">
      ${options.map((option) => {
        const optionValue = Array.isArray(option) ? option[0] : option;
        const optionLabel = Array.isArray(option) ? option[1] : option;
        return `<option value="${this.escapeHtml(optionValue)}" ${optionValue === value ? "selected" : ""}>${this.escapeHtml(optionLabel)}</option>`;
      }).join("")}
    </select></div>`;
  }

  aiProfiles() {
    if (this._aiProfileDraft) return this._aiProfileDraft;
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const source = aiState?.attributes?.user_profiles;
    const defaults = {
      schema_version: 2,
      profiles: {
        morning_sale: { enabled: false, type: "sale", name: "Poranna sprzedaż", active_days: [], start: "06:00", end: "09:00", priority: "normal", goal_character: "preferred", allow_partial: true, minimum_confidence: 50, note: "", target_energy_kwh: 0, target_basis: "battery_to_grid", min_price: 0, preferred_power_w: "", distribution_method: "best_hours", min_soc_after: 30, allow_earlier_grid_charge: false, min_net_result: 0 },
        evening_sale: { enabled: false, type: "sale", name: "Wieczorna sprzedaż", active_days: [], start: "17:00", end: "22:00", priority: "normal", goal_character: "preferred", allow_partial: true, minimum_confidence: 50, note: "", target_energy_kwh: 0, target_basis: "battery_to_grid", min_price: 0, preferred_power_w: "", distribution_method: "best_hours", min_soc_after: 30, allow_earlier_grid_charge: false, min_net_result: 0 },
        charging: { enabled: false, type: "charging", name: "Ładowanie", active_days: [], start: "22:00", end: "06:00", priority: "normal", goal_character: "preferred", allow_partial: true, minimum_confidence: 50, note: "", source: "auto", target_type: "soc", target_value: 80, deadline: "06:00", max_effective_price: 0, max_grid_energy_kwh: "", preferred_power_w: "", purpose: "mixed", charge_missing_only: true, use_corrected_pv: true, preserve_pv_room: true, minimum_free_room_kwh: 0, profitable_only: true },
      },
    };
    const profiles = {};
    Object.entries(defaults.profiles).forEach(([key, value]) => {
      profiles[key] = { ...value, ...(source?.profiles?.[key] || {}) };
      if (!["low", "normal", "high"].includes(String(profiles[key].priority))) profiles[key].priority = "normal";
      if (key === "charging") {
        profiles[key].purpose = ({
          general: "mixed",
          home_reserve: "reserve",
          morning_sale: "sale",
          evening_sale: "sale",
          both_sales: "sale",
          cheap_home: "home",
        })[profiles[key].purpose] || profiles[key].purpose || "mixed";
      }
    });
    this._aiProfileDraft = { schema_version: 2, profiles };
    return this._aiProfileDraft;
  }

  aiProfileInput(profileId, field, label, value, type = "text", unit = "") {
    const inputType = type === "number" ? 'type="text" inputmode="decimal"' : `type="${type}"`;
    return `<div class="settings-row"><span>${this.escapeHtml(label)}</span><label class="field compact-field"><input data-ai-profile="${profileId}" data-ai-profile-field="${field}" ${inputType} value="${this.escapeHtml(value ?? "")}"><span>${this.escapeHtml(unit)}</span></label></div>`;
  }

  aiProfileCheck(profileId, field, label, value) {
    return `<div class="settings-row"><span>${this.escapeHtml(label)}</span><input data-ai-profile="${profileId}" data-ai-profile-field="${field}" type="checkbox" ${value ? "checked" : ""}></div>`;
  }

  aiProfileSelect(profileId, field, label, options, value) {
    return `<div class="settings-row"><span>${this.escapeHtml(label)}</span><select data-ai-profile="${profileId}" data-ai-profile-field="${field}">${options.map(([key, text]) => `<option value="${this.escapeHtml(key)}" ${key === value ? "selected" : ""}>${this.escapeHtml(text)}</option>`).join("")}</select></div>`;
  }

  aiProfileCommon(profileId, profile) {
    const dayNames = [["0", "Pon"], ["1", "Wt"], ["2", "Śr"], ["3", "Czw"], ["4", "Pt"], ["5", "Sob"], ["6", "Niedz"]];
    const selected = new Set(Array.isArray(profile.active_days) ? profile.active_days.map(String) : []);
    return `${this.aiProfileCheck(profileId, "enabled", "Włącz profil", profile.enabled)}
      <div class="settings-row ai-days-row"><span>Aktywne dni</span><div class="ai-day-presets"><button type="button" data-ai-profile-days="${profileId}" data-days="">Codziennie</button><button type="button" data-ai-profile-days="${profileId}" data-days="0,1,2,3,4">Dni robocze</button><button type="button" data-ai-profile-days="${profileId}" data-days="5,6">Weekend</button></div></div>
      <div class="ai-weekdays">${dayNames.map(([key, label]) => `<label><input type="checkbox" data-ai-profile-day="${profileId}" value="${key}" ${selected.has(key) ? "checked" : ""}>${label}</label>`).join("")}</div>
      ${this.aiProfileInput(profileId, "start", "Godzina od", profile.start, "time")}
      ${this.aiProfileInput(profileId, "end", "Godzina do", profile.end, "time")}
      ${this.aiProfileSelect(profileId, "priority", "Priorytet", [["low", "Niski"], ["normal", "Normalny"], ["high", "Wysoki"]], profile.priority)}
      ${this.aiProfileSelect(profileId, "goal_character", "Charakter celu", [["preferred", "Preferowany"], ["required", "Wymagany w granicach bezpieczeństwa"]], profile.goal_character)}
      ${this.aiProfileCheck(profileId, "allow_partial", "Zezwalaj na częściową realizację", profile.allow_partial)}
      ${this.aiProfileInput(profileId, "minimum_confidence", "Minimalna pewność rekomendacji", profile.minimum_confidence, "number", "%")}
      <div class="settings-row ai-note-row"><span>Notatka lokalna</span><textarea data-ai-profile="${profileId}" data-ai-profile-field="note" maxlength="500">${this.escapeHtml(profile.note || "")}</textarea></div>`;
  }

  renderAiSaleProfile(profileId) {
    const profile = this.aiProfiles().profiles[profileId];
    const planner = this.aiPlannerData(this._lastSlots || []);
    const impact = (planner.profile_impacts || []).find((item) => item.profile_id === profileId);
    const validation = profile.start === profile.end ? "Błąd: przedział nie może być pusty." : "Konfiguracja lokalna jest kompletna.";
    return `<div class="ai-settings-pane"><div class="hint">Profil jest polityką Optimizer Core. Sam zapis nie zmienia Deye ani harmonogramu TOU.</div>
      <div class="ai-profile-summary"><div><span>Stan</span><strong>${profile.enabled ? "Włączony" : "Wyłączony"}</strong></div><div><span>Okno</span><strong>${this.escapeHtml(profile.start)}–${this.escapeHtml(profile.end)}</strong></div><div><span>Planowana realizacja</span><strong>${impact ? `${this.formatNumber(impact.planned_energy_kwh, 2)} kWh` : "brak planu"}</strong></div><div><span>Walidacja</span><strong class="${validation.startsWith("Błąd") ? "bad" : "good"}">${validation}</strong></div></div>
      ${this.aiProfileCommon(profileId, profile)}
      ${this.aiProfileInput(profileId, "target_energy_kwh", "Docelowa energia sprzedaży", profile.target_energy_kwh, "number", "kWh")}
      ${this.aiProfileSelect(profileId, "target_basis", "Sposób liczenia celu", [["battery_to_grid", "Energia z baterii do sieci"], ["total_export", "Całkowity eksport do sieci"]], profile.target_basis)}
      ${this.aiProfileInput(profileId, "min_price", "Minimalna cena sprzedaży", profile.min_price, "number", "zł/kWh")}
      ${this.aiProfileInput(profileId, "preferred_power_w", "Maksymalna moc profilu", profile.preferred_power_w ?? "", "number", "W")}
      ${this.aiProfileSelect(profileId, "distribution_method", "Sposób rozłożenia energii", [["best_hours", "Najwyższe ceny najpierw"], ["even", "Równomiernie w oknie"], ["constant_power", "Możliwie stała moc"]], profile.distribution_method)}
      ${this.aiProfileInput(profileId, "min_soc_after", "Minimalny SOC po oknie", profile.min_soc_after, "number", "%")}
      ${this.aiProfileCheck(profileId, "allow_earlier_grid_charge", "Zezwalaj na wcześniejsze ładowanie z sieci", profile.allow_earlier_grid_charge)}
      ${this.aiProfileInput(profileId, "min_net_result", "Minimalny wynik netto cyklu", profile.min_net_result, "number", "zł")}
      <button class="wide-action" data-save-ai-profiles="1">Zapisz wszystkie profile</button>${this._aiProfileStatus ? `<div class="hint">${this.escapeHtml(this._aiProfileStatus)}</div>` : ""}</div>`;
  }

  renderAiChargeProfile() {
    const profileId = "charging";
    const profile = this.aiProfiles().profiles[profileId];
    const energyTarget = profile.target_type === "energy";
    return `<div class="ai-settings-pane"><div class="hint">Optimizer wykorzysta profil wraz z prognozą PV, domu i efektywnym kosztem taryfy. Sam zapis nie uruchamia ładowania.</div>
      ${this.aiProfileCommon(profileId, profile)}
      ${this.aiProfileSelect(profileId, "source", "Źródło ładowania", [["auto", "Automatycznie"], ["pv", "Tylko PV"], ["grid", "Tylko sieć"], ["pv_and_grid", "PV i sieć"]], profile.source)}
      ${this.aiProfileSelect(profileId, "target_type", "Cel ładowania", [["soc", "Docelowy SOC"], ["energy", "Docelowa energia doładowania"]], profile.target_type)}
      ${this.aiProfileInput(profileId, "target_value", energyTarget ? "Docelowa energia doładowania" : "Docelowy SOC", profile.target_value, "number", energyTarget ? "kWh" : "%")}
      ${this.aiProfileInput(profileId, "deadline", "Cel najpóźniej do", profile.deadline, "time")}
      ${this.aiProfileInput(profileId, "max_effective_price", "Maksymalna efektywna cena zakupu", profile.max_effective_price, "number", "zł/kWh")}
      ${this.aiProfileInput(profileId, "max_grid_energy_kwh", "Maksymalna energia z sieci", profile.max_grid_energy_kwh ?? "", "number", "kWh")}
      ${this.aiProfileInput(profileId, "preferred_power_w", "Opcjonalny limit mocy profilu", profile.preferred_power_w ?? "", "number", "W")}
      ${this.aiProfileSelect(profileId, "purpose", "Przeznaczenie ładowania", [["mixed", "Automatycznie / cel mieszany"], ["sale", "Późniejsza sprzedaż"], ["home", "Zużycie domu"], ["reserve", "Rezerwa bezpieczeństwa"]], profile.purpose)}
      ${this.aiProfileCheck(profileId, "charge_missing_only", "Doładuj tylko brakującą energię", profile.charge_missing_only)}
      ${this.aiProfileCheck(profileId, "use_corrected_pv", "Uwzględniaj skorygowaną prognozę PV", profile.use_corrected_pv)}
      ${this.aiProfileCheck(profileId, "preserve_pv_room", "Zachowaj miejsce na prognozowaną produkcję PV", profile.preserve_pv_room)}
      ${this.aiProfileInput(profileId, "minimum_free_room_kwh", "Minimalne wolne miejsce na PV", profile.minimum_free_room_kwh, "number", "kWh")}
      ${this.aiProfileCheck(profileId, "profitable_only", "Ładuj z sieci tylko przy dodatnim wyniku cyklu", profile.profitable_only)}
      <button class="wide-action" data-save-ai-profiles="1">Zapisz wszystkie profile</button>${this._aiProfileStatus ? `<div class="hint">${this.escapeHtml(this._aiProfileStatus)}</div>` : ""}</div>`;
  }

  renderAiGeneralSettings() {
    const settings = this.aiSettings();
    return `<div class="ai-settings-pane"><div class="hint">Lokalny Optimizer Core tworzy wyłącznie propozycje. Zapis do Deye wymaga wyboru godzin, lokalnej walidacji i ręcznego potwierdzenia.</div>
      ${this.aiCheck("enabled", "Włącz inteligentne planowanie", settings.enabled)}
      ${this.row("Tryb działania", "Sugestie z ręcznym zatwierdzeniem")}
      ${this.aiSelect("strategy", "Priorytet", [["balanced", "Zrównoważony"], ["profit", "Maksymalny zysk"], ["autoconsumption", "Maksymalna autokonsumpcja"]], settings.strategy)}
      ${this.aiCheck("forecastEnabled", "Uwzględniaj prognozę Solcast", settings.forecastEnabled)}
      ${this.aiNumber("forecastMargin", "Margines bezpieczeństwa prognozy", settings.forecastMargin, "%")}
      ${this.aiCheck("realPv", "Porównuj z realną produkcją PV", settings.realPv)}
      ${this.aiCheck("history", "Uwzględniaj historię produkcji i sprzedaży", settings.history)}
      ${this.aiCheck("prices", "Uwzględniaj ceny energii", settings.prices)}
      ${this.aiNumber("minSellPrice", "Minimalna cena sprzedaży", settings.minSellPrice, "zł/kWh")}
      ${this.aiNumber("maxBuyPrice", "Maksymalna cena zakupu", settings.maxBuyPrice, "zł/kWh")}
      ${this.aiNumber("minSoc", "Minimalny SOC", settings.minSoc, "%")}
      ${this.aiNumber("targetSoc", "Docelowy SOC magazynu", settings.targetSoc, "%")}
      ${this.aiNumber("batteryCapacityKwh", "Pojemność użytkowa magazynu", settings.batteryCapacityKwh, "kWh")}
      ${this.aiNumber("batteryEfficiency", "Sprawność pełnego cyklu", settings.batteryEfficiency, "%")}
      ${this.aiNumber("reserveKwh", "Dodatkowa rezerwa ponad minimalny SOC", settings.reserveKwh, "kWh")}
      ${this.aiNumber("maxSellPower", "Maksymalna moc planu AI", settings.maxSellPower, "W")}
      ${this.aiNumber("minimumAutoSellPowerW", "Minimalna moc automatycznej sprzedaży", settings.minimumAutoSellPowerW ?? 1000, "W")}
      <div class="hint">Minimum dotyczy wyłącznie automatycznych propozycji Core i nie ogranicza ręcznego sterowania.</div>
      ${this.aiNumber("priceEquivalenceBand", "Różnica ceny uznawana za zbliżoną", settings.priceEquivalenceBand ?? 0.05, "zł/kWh")}
      <div class="hint">Gdy różnica ceny mieści się w tym progu, Core może równomierniej rozłożyć sprzedaż, aby obniżyć szczytową moc baterii.</div>
      ${this.aiNumber("batteryCycleCostPerKwh", "Koszt zużycia magazynu", settings.batteryCycleCostPerKwh ?? 0, "zł/kWh")}
      ${this.aiNumber("terminalEnergyValuePerKwh", "Konserwatywna wartość energii końcowej", settings.terminalEnergyValuePerKwh ?? 0, "zł/kWh")}
      ${this.aiCheck("allowGridCharge", "AI może sugerować ładowanie z sieci", settings.allowGridCharge)}
      ${this.aiCheck("allowBatterySell", "AI może sugerować sprzedaż z baterii", settings.allowBatterySell)}
      ${this.aiCheck("allowDeyeMode", "AI może sugerować zmianę trybu Deye", settings.allowDeyeMode)}</div>`;
  }

  renderAiSettingsPanel() {
    const section = this._aiSettingsSection || "general";
    const tabs = [
      ["general", "Ogólne"], ["morning_sale", "Poranna sprzedaż"],
      ["evening_sale", "Wieczorna sprzedaż"], ["charging", "Ładowanie"],
      ["api", "Asystent AI przez API"],
    ].map(([key, label]) => `<button class="${section === key ? "active" : ""}" data-ai-settings-section="${key}">${label}</button>`).join("");
    let body = this.renderAiGeneralSettings();
    if (section === "morning_sale" || section === "evening_sale") body = this.renderAiSaleProfile(section);
    if (section === "charging") body = this.renderAiChargeProfile();
    if (section === "api") body = this.renderAiApiSettings ? this.renderAiApiSettings() : '<div class="hint">Asystent API jest opcjonalny. Lokalny Optimizer Core działa bez niego.</div>';
    return `<div class="settings-tabs ai-settings-tabs">${tabs}</div>${body}`;
  }

  aiApiContext() {
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    return aiState?.attributes?.api_assistant || {};
  }

  aiApiDraft() {
    if (this._aiApiDraft) return this._aiApiDraft;
    const config = this.aiApiContext().config || {};
    this._aiApiDraft = {
      enabled: Boolean(config.enabled),
      provider: config.provider || "openrouter",
      model: config.model || "",
      endpoint: config.provider === "custom" ? (config.endpoint || "") : "",
      role: config.role || "review",
      hourly_only: config.hourly_only !== false,
      remove_entity_names: config.remove_entity_names !== false,
      remove_exact_location: config.remove_exact_location !== false,
      max_history_hours: config.max_history_hours ?? 0,
    };
    return this._aiApiDraft;
  }

  renderAiApiSettings() {
    const context = this.aiApiContext();
    const draft = this.aiApiDraft();
    const custom = draft.provider === "custom";
    const analysis = context.last_analysis;
    const providerNote = draft.provider === "opencode"
      ? "Preset używa oficjalnego OpenCode Console Inference API. Wklej osobny klucz usługi; integracja nie odczytuje auth.json, sesji ani konfiguracji lokalnego OpenCode."
      : "Dane instalacji są wysyłane wyłącznie po włączeniu asystenta. Lokalny plan pozostaje nadrzędny.";
    return `<div class="ai-settings-pane ai-api-settings"><div class="hint">${this.escapeHtml(providerNote)}</div>
      <div class="ai-profile-summary"><div><span>Status połączenia</span><strong>${this.escapeHtml(this.aiUiText(context.status || "disabled"))}</strong></div><div><span>Model użyty</span><strong>${this.escapeHtml(context.model || draft.model || "brak")}</strong></div><div><span>Czas odpowiedzi</span><strong>${context.response_ms === undefined ? "brak" : `${this.formatNumber(context.response_ms, 0)} ms`}</strong></div><div><span>Walidacja odpowiedzi</span><strong>${this.escapeHtml(context.json_schema ? this.aiUiText(context.json_schema) : "brak testu")}</strong></div></div>
      <div class="settings-row"><span>Włącz asystenta AI</span><input data-ai-api-field="enabled" type="checkbox" ${draft.enabled ? "checked" : ""}></div>
      <div class="settings-row"><span>Dostawca</span><select data-ai-api-field="provider"><option value="gemini" ${draft.provider === "gemini" ? "selected" : ""}>Google Gemini</option><option value="openrouter" ${draft.provider === "openrouter" ? "selected" : ""}>OpenRouter</option><option value="openai" ${draft.provider === "openai" ? "selected" : ""}>OpenAI</option><option value="opencode" ${draft.provider === "opencode" ? "selected" : ""}>OpenCode / OpenCode Go</option><option value="custom" ${custom ? "selected" : ""}>Własny endpoint zgodny z OpenAI API</option></select></div>
      <div class="settings-row"><span>Klucz API</span><label class="field compact-field"><input data-ai-api-field="api_key" type="password" autocomplete="new-password" value="" placeholder="${context.config?.api_key_configured ? "Klucz zapisany — pozostaw puste, aby zachować" : "Wklej osobny klucz API"}"><span>🔒</span></label></div>
      <div class="settings-row"><span>Model</span><input data-ai-api-field="model" type="text" value="${this.escapeHtml(draft.model)}" placeholder="Identyfikator modelu z dokumentacji dostawcy"></div>
      ${custom ? `<div class="settings-row"><span>Własny endpoint HTTPS</span><input data-ai-api-field="endpoint" type="url" value="${this.escapeHtml(draft.endpoint)}" placeholder="https://…/v1/chat/completions"></div>` : ""}
      <div class="settings-row"><span>Rola modelu</span><select data-ai-api-field="role"><option value="explain" ${draft.role === "explain" ? "selected" : ""}>Tylko uzasadnia plan</option><option value="review" ${draft.role === "review" ? "selected" : ""}>Sprawdza plan i proponuje alternatywę</option><option value="experimental" ${draft.role === "experimental" ? "selected" : ""}>Zaawansowana analiza eksperymentalna</option></select></div>
      <h3>Prywatność</h3>
      <div class="settings-row"><span>Wysyłaj tylko dane godzinowe</span><input data-ai-api-field="hourly_only" type="checkbox" ${draft.hourly_only ? "checked" : ""}></div>
      <div class="settings-row"><span>Usuń nazwy encji i urządzeń</span><input data-ai-api-field="remove_entity_names" type="checkbox" ${draft.remove_entity_names ? "checked" : ""}></div>
      <div class="settings-row"><span>Nie wysyłaj dokładnej lokalizacji</span><input data-ai-api-field="remove_exact_location" type="checkbox" ${draft.remove_exact_location ? "checked" : ""}></div>
      <div class="settings-row"><span>Maksymalny zakres historii</span><label class="field compact-field"><input data-ai-api-field="max_history_hours" type="text" inputmode="numeric" value="${this.escapeHtml(draft.max_history_hours)}"><span>h</span></label></div>
      <div class="diagnostic-actions"><button data-save-ai-api="1">Zapisz konfigurację</button><button data-test-ai-api="1">Testuj połączenie</button><button data-analyze-ai-api="1">Analizuj ponownie</button></div>
      ${context.last_error ? `<div class="hint bad">${this.escapeHtml(context.last_error)}</div>` : ""}
      ${this._aiApiMessage ? `<div class="hint">${this.escapeHtml(this._aiApiMessage)}</div>` : ""}
      ${analysis ? `<section class="diagnostic-section"><h3>Ostatnia opinia AI — niezastosowana</h3><p>${this.escapeHtml(analysis.summary || "Brak podsumowania.")}</p><p><b>Ocena:</b> ${this.escapeHtml(this.aiUiText(analysis.plan_assessment || "brak"))} · <b>Wariant:</b> ${this.escapeHtml(this.aiUiText(analysis.best_option || "brak"))}</p><p><b>Powody:</b> ${this.escapeHtml((analysis.reasons || []).join(" · ") || "brak")}</p><p><b>Ryzyka:</b> ${this.escapeHtml((analysis.risks || []).join(" · ") || "brak")}</p><div class="hint">Wymaga lokalnej walidacji. Zewnętrzne AI otrzymuje polecenie zwracania odpowiedzi po polsku i nie może bezpośrednio zapisać niczego do Deye ani harmonogramu.</div></section>` : ""}</div>`;
  }

  collectAiApiDraft() {
    const draft = { ...this.aiApiDraft() };
    this.querySelectorAll("[data-ai-api-field]").forEach((el) => {
      const field = el.dataset.aiApiField;
      if (field === "api_key") return;
      if (el.type === "checkbox") draft[field] = el.checked;
      else if (field === "max_history_hours") draft[field] = this.asNumber(el.value) ?? el.value;
      else draft[field] = el.value;
    });
    this._aiApiDraft = draft;
    return draft;
  }

  async saveAiApiSettings() {
    const draft = this.collectAiApiDraft();
    const secret = this.querySelector('[data-ai-api-field="api_key"]')?.value || "";
    try {
      await this.callService("deye_energy_manager", "save_ai_api_settings", {
        data: JSON.stringify({ ...draft, api_key: secret }),
      });
      this._aiApiMessage = "Konfiguracja zapisana bez uruchamiania Deye. Puste pole klucza zachowuje poprzedni sekret.";
    } catch (error) {
      this._aiApiMessage = `Błąd konfiguracji: ${error?.message || error}`;
    }
    const input = this.querySelector('[data-ai-api-field="api_key"]');
    if (input) input.value = "";
    this.renderDialogOnly();
  }

  async runAiApiService(service) {
    this._aiApiMessage = service === "test_ai_api" ? "Trwa bezpieczny test bez danych instalacji…" : "Trwa analiza ostatniego lokalnego planu…";
    this.renderDialogOnly();
    try {
      await this.callService("deye_energy_manager", service, {});
      this._aiApiMessage = "Żądanie zakończone. Status zostanie odświeżony z backendu.";
    } catch (error) {
      this._aiApiMessage = `Błąd API: ${error?.message || error}`;
    }
    this.render();
  }

  collectAiProfiles() {
    const draft = this.aiProfiles();
    this.querySelectorAll("[data-ai-profile][data-ai-profile-field]").forEach((el) => {
      const profile = draft.profiles[el.dataset.aiProfile];
      if (!profile) return;
      const field = el.dataset.aiProfileField;
      if (el.type === "checkbox") profile[field] = el.checked;
      else if (el.inputMode === "decimal") profile[field] = el.value === "" ? null : (this.asNumber(el.value) ?? el.value);
      else profile[field] = el.value;
    });
    Object.keys(draft.profiles).forEach((profileId) => {
      const boxes = [...this.querySelectorAll(`[data-ai-profile-day="${profileId}"]`)];
      if (boxes.length) draft.profiles[profileId].active_days = boxes.filter((box) => box.checked).map((box) => box.value);
    });
    return draft;
  }

  validateAiProfiles(profiles) {
    for (const [key, profile] of Object.entries(profiles.profiles || {})) {
      if (!profile.start || !profile.end || profile.start === profile.end) return `Profil ${key}: przedział czasu nie może być pusty.`;
      const confidence = this.asNumber(profile.minimum_confidence);
      if (confidence === null || confidence < 0 || confidence > 100) return `Profil ${key}: pewność musi mieścić się w zakresie 0–100%.`;
      if (key !== "charging") {
        const target = this.asNumber(profile.target_energy_kwh);
        const price = this.asNumber(profile.min_price);
        const soc = this.asNumber(profile.min_soc_after);
        if (target === null || target < 0) return `Profil ${key}: cel kWh nie może być ujemny.`;
        if (price === null || price < 0) return `Profil ${key}: cena nie może być ujemna.`;
        if (soc === null || soc < 0 || soc > 100) return `Profil ${key}: SOC musi mieścić się w zakresie 0–100%.`;
      } else {
        const target = this.asNumber(profile.target_value);
        if (target === null || target <= 0 || (profile.target_type === "soc" && target > 100)) return "Profil ładowania: nieprawidłowy cel.";
      }
    }
    return "";
  }

  async saveAiProfiles() {
    const profiles = this.collectAiProfiles();
    const error = this.validateAiProfiles(profiles);
    if (error) {
      this._aiProfileStatus = error;
      this.renderDialogOnly();
      return;
    }
    try {
      await this.callService("deye_energy_manager", "save_ai_profiles", { data: JSON.stringify(profiles) });
      this._aiProfileStatus = "Zapisano. Zmiana wpłynie na kolejną lokalną analizę; Deye nie został zmieniony.";
    } catch (errorValue) {
      this._aiProfileStatus = `Błąd zapisu: ${errorValue?.message || errorValue}`;
    }
    this.renderDialogOnly();
  }

  collectBulkEditState() {
    const panel = this.querySelector(".multi-dialog") || this.querySelector(".bulk-panel");
    if (!panel) return null;
    const value = (name, fallback = "") => panel.querySelector(`[data-raw="${name}"]`)?.value ?? fallback;
    const checked = (name) => Boolean(panel.querySelector(`[data-apply-field="${name}"]`)?.checked);
    const state = {
      values: {
        active: value("multi-active", "on"),
        mode: this.normalizeManagerMode(value("multi-mode", "Sprzedaż")),
        sellPower: value("multi-sell-power", 5000),
        dischargeCurrent: value("multi-discharge-current", 120),
        chargeCurrent: value("multi-charge-current", 0),
        minSoc: value("multi-min-soc", 40),
        minSellPrice: value("multi-min-sell-price", 0),
      },
      fields: {},
    };
    ["active", "mode", "sellPower", "dischargeCurrent", "chargeCurrent", "minSoc", "minSellPrice"].forEach((name) => {
      state.fields[name] = checked(name);
    });
    this._bulkEditDraft = { ...state.values };
    this._bulkEditFields = { ...state.fields };
    return state;
  }

  physicalTouDiagnostics() {
    const attrs = this.diagnosticsAttributes();
    return Array.isArray(attrs.physical_tou) ? attrs.physical_tou : [];
  }

  touCapabilitiesDiagnostics() {
    const rows = this.diagnosticsAttributes()?.tou_capabilities;
    return Array.isArray(rows) ? rows : [];
  }

  touTransactionDiagnostics() {
    const value = this.diagnosticsAttributes()?.tou_transaction;
    return value && typeof value === "object" ? value : {};
  }

  touReverseSyncDiagnostics() {
    const value = this.diagnosticsAttributes()?.tou_reverse_sync;
    return value && typeof value === "object" ? value : {};
  }

  touCapabilityRow(slot) {
    return this.touCapabilitiesDiagnostics().find((row) => Number(row.slot_index) === Number(slot)) || null;
  }

  physicalTouRow(slot) {
    return this.physicalTouDiagnostics().find((row) => Number(row.range) === Number(slot)) || null;
  }

  touFieldNames() {
    return ["start", "end", "soc", "grid_charge"];
  }

  touFieldCapability(slot, field) {
    return this.touCapabilityRow(slot)?.fields?.[field] || null;
  }

  touFieldDiagnostics(slot, field) {
    const physical = this.physicalTouRow(slot);
    const current = physical?.fields?.[field] || {};
    return {
      capability: this.touFieldCapability(slot, field) || current.capability || {},
      actual: current.actual ?? null,
      expected: current.expected ?? null,
      status: String(current.status || "unavailable"),
    };
  }

  touWritePending() {
    return this.touTransactionDiagnostics().tou_write_pending === true;
  }

  touOperationStatus() {
    const transaction = this.touTransactionDiagnostics();
    return String(transaction.operation_status || transaction.tou_operation_status || "idle");
  }

  touOperationError() {
    const transaction = this.touTransactionDiagnostics();
    const reverse = this.touReverseSyncDiagnostics();
    const value = reverse.reverse_sync_last_error && reverse.reverse_sync_last_error !== "none"
      ? reverse.reverse_sync_last_error
      : transaction.tou_last_error;
    return value && value !== "none" ? String(value) : "";
  }

  touControlBlocked(row = null) {
    const control = this.diagnosticsAttributes()?.control || {};
    return control.control_enabled === false
      || String(control.control_status || "") !== "Aktywne"
      || row?.blocked_by_master_control === true;
  }

  touStatusLabel(status) {
    return ({
      unchanged: "Bez zmian",
      waiting: "Oczekiwanie",
      confirmed: "Potwierdzono",
      rolled_back: "Przywrócono",
      mismatch: "Niezgodność",
      unavailable: "Niedostępne",
    })[String(status)] || "Niedostępne";
  }

  touOperationStatusLabel(status = this.touOperationStatus()) {
    return ({
      idle: "Brak aktywnego zapisu",
      writing: "Zapisywanie",
      confirming: "Oczekiwanie na potwierdzenie",
      waiting: "Oczekiwanie na potwierdzenie",
      confirmed: "Potwierdzono",
      rollback: "Przywracanie poprzednich ustawień",
      rollback_failed: "Nie udało się przywrócić ustawień",
      mismatch: "Niezgodność",
      unavailable: "Niedostępne",
    })[String(status)] || "Brak aktywnego zapisu";
  }

  touReverseStatusLabel(status) {
    return ({
      idle: "Brak aktywnej synchronizacji",
      applying: "Synchronizowanie Harmonogramu",
      confirmed: "Potwierdzona",
      rollback: "Wycofana",
      rollback_failed: "Nie udało się przywrócić ustawień",
    })[String(status)] || "Brak danych";
  }

  touDiagnosticsSignature() {
    return JSON.stringify({
      capabilities: this.touCapabilitiesDiagnostics(),
      physical: this.physicalTouDiagnostics(),
      transaction: this.touTransactionDiagnostics(),
      reverse: this.touReverseSyncDiagnostics(),
      control: this.diagnosticsAttributes()?.control || {},
    });
  }

  touActualValues(slot) {
    const values = {};
    this.touFieldNames().forEach((field) => {
      const data = this.touFieldDiagnostics(slot, field);
      if (data.capability.supported !== true) return;
      values[field] = field === "grid_charge" ? Boolean(data.actual) : data.actual;
    });
    return values;
  }

  resetTouEditor() {
    this._touEditDraft = null;
    this._touEditOriginal = null;
    this._touSaveError = "";
    this._touAwaitingConfirmation = null;
  }

  openTouEditor(slot) {
    const actual = this.touActualValues(slot);
    this._touEditOriginal = { slot: Number(slot), values: { ...actual } };
    this._touEditDraft = { slot: Number(slot), values: { ...actual } };
    this._touSaveError = "";
    this._dialog = { type: "tou", idx: Number(slot) };
  }

  ensureTouEditorDraft(slot) {
    if (this._touEditDraft?.slot === Number(slot) && this._touEditOriginal?.slot === Number(slot)) return;
    const actual = this.touActualValues(slot);
    this._touEditOriginal = { slot: Number(slot), values: { ...actual } };
    this._touEditDraft = { slot: Number(slot), values: { ...actual } };
  }

  refreshTouEditorFromActual(slot, clearError = true) {
    const actual = this.touActualValues(slot);
    this._touEditOriginal = { slot: Number(slot), values: { ...actual } };
    this._touEditDraft = { slot: Number(slot), values: { ...actual } };
    if (clearError) this._touSaveError = "";
  }

  syncTouEditorAfterDiagnostics() {
    if (!this._touAwaitingConfirmation) return;
    const slot = Number(this._touAwaitingConfirmation);
    const status = this.touOperationStatus();
    if (status === "confirmed") {
      this.refreshTouEditorFromActual(slot);
      this._touAwaitingConfirmation = null;
      this._saveStatus = "saved";
      this._saveMessage = "Potwierdzono zapis Deye Time Of Use";
    } else if (["rollback", "rollback_failed", "mismatch", "unavailable"].includes(status)) {
      this.refreshTouEditorFromActual(slot, false);
      this._touAwaitingConfirmation = null;
      this._saveStatus = "error";
      this._touSaveError = this.touOperationError() || this.touOperationStatusLabel(status);
    }
  }

  collectTouEditorDraft(slot) {
    this.ensureTouEditorDraft(slot);
    const values = this._touEditDraft.values;
    const controls = {
      start: this.querySelector('[data-tou-field="start"]'),
      end: this.querySelector('[data-tou-field="end"]'),
      soc: this.querySelector('[data-tou-field="soc"]'),
      grid_charge: this.querySelector('[data-tou-field="grid_charge"]'),
    };
    Object.entries(controls).forEach(([field, control]) => {
      if (!control) return;
      if (field === "grid_charge") values[field] = String(control.value) === "on";
      else if (field === "soc") values[field] = this.asNumber(control.value);
      else values[field] = String(control.value || "").slice(0, 5);
    });
    return values;
  }

  buildTouPartialPayload(slot) {
    this.ensureTouEditorDraft(slot);
    const payload = { slot: Number(slot) };
    const draft = this._touEditDraft.values;
    const original = this._touEditOriginal.values;
    const timePattern = /^(?:[01]\d|2[0-3]):00$/;
    this.touFieldNames().forEach((field) => {
      const capability = this.touFieldCapability(slot, field);
      if (capability?.supported !== true || capability.writable !== true) return;
      const current = draft[field];
      const previous = original[field];
      const changed = field === "soc"
        ? Number(current) !== Number(previous)
        : field === "grid_charge"
          ? Boolean(current) !== Boolean(previous)
          : String(current ?? "") !== String(previous ?? "");
      if (!changed) return;
      if ((field === "start" || field === "end") && !timePattern.test(String(current || ""))) {
        throw new Error("Godziny Od i Do muszą wskazywać pełną godzinę z minutami 00.");
      }
      if (field === "soc" && (!Number.isFinite(Number(current)) || Number(current) < 0 || Number(current) > 100)) {
        throw new Error("SOC Deye TOU musi mieścić się w zakresie 0–100%.");
      }
      if (field === "grid_charge") payload.grid_charge = Boolean(current);
      else if (field === "soc") payload.soc = Number(current);
      else payload[field] = String(current).slice(0, 5);
    });
    return payload;
  }

  diagnosticsAttributes() {
    return this._hass?.states?.[this.entity("sensor", "diagnostics")]?.attributes || {};
  }

  effectiveInverterMaxPowerW() {
    const attrs = this.diagnosticsAttributes();
    const configured = this.asNumber(attrs?.power_limits?.effective_inverter_max_power_w);
    return Number.isFinite(configured) && configured > 0 ? configured : 13000;
  }

  fullTouCapability() {
    return this.diagnosticsAttributes()?.capabilities?.full_tou || { ok: false, supported: false };
  }

  mappingPlanDiagnostics() {
    const plan = this.diagnosticsAttributes()?.mapping_plan;
    return Array.isArray(plan) ? plan : [];
  }

  hasWritablePhysicalTou(slot = null) {
    const rows = slot === null ? this.touCapabilitiesDiagnostics() : [this.touCapabilityRow(slot)].filter(Boolean);
    return this.hasService("deye_energy_manager", "set_tou_slot")
      && !this._touSaving
      && !this.touWritePending()
      && rows.some((row) => row.read_only !== true
        && !this.touControlBlocked(row)
        && this.touFieldNames().some((field) => row.fields?.[field]?.writable === true));
  }

  touGridLabel(value) {
    const normalized = String(value ?? "").trim().toLowerCase();
    if (["on", "grid", "allow grid", "both"].includes(normalized)) return "tak";
    if (["off", "disabled", "no grid or gen"].includes(normalized)) return "nie";
    return value ? String(value) : "brak";
  }

  touFieldLabel(field) {
    return ({
      start: "Od",
      end: "Do",
      soc: "SOC Deye TOU",
      grid_charge: "Ładowanie z sieci",
    })[field] || field;
  }

  formatTouFieldValue(field, value) {
    if (value === null || value === undefined || value === "") return "Niedostępne";
    if (field === "grid_charge") return Boolean(value) ? "Tak" : "Nie";
    if (field === "soc") return `${this.escapeHtml(String(value))}%`;
    return this.escapeHtml(String(value).slice(0, 5));
  }

  touEditorFieldHtml(slot, field) {
    const data = this.touFieldDiagnostics(slot, field);
    const capability = data.capability;
    if (capability.supported !== true) return "";
    const currentAvailable = capability.current_available !== false && data.actual !== null;
    const draftValue = this._touEditDraft?.values?.[field];
    const writable = capability.writable === true;
    let control;
    if (!currentAvailable) {
      control = `<span class="bad" data-tou-unavailable="${field}">Niedostępne</span>`;
    } else if (!writable) {
      control = `<span data-tou-readonly="${field}">${this.formatTouFieldValue(field, data.actual)}</span>`;
    } else if (field === "start" || field === "end") {
      control = `<input data-tou-field="${field}" type="time" step="3600" value="${this.escapeHtml(String(draftValue ?? data.actual).slice(0, 5))}">`;
    } else if (field === "soc") {
      control = `<input data-tou-field="soc" type="number" min="0" max="100" step="1" value="${this.escapeHtml(String(draftValue ?? data.actual))}"><span class="unit">%</span>`;
    } else {
      control = `<select data-tou-field="grid_charge"><option value="off" ${Boolean(draftValue ?? data.actual) ? "" : "selected"}>NIE</option><option value="on" ${Boolean(draftValue ?? data.actual) ? "selected" : ""}>TAK</option></select>`;
    }
    const expected = data.expected === null || data.expected === undefined
      ? ""
      : `<span>Oczekiwana wartość: <strong>${this.formatTouFieldValue(field, data.expected)}</strong></span>`;
    return `<div class="settings-row tou-editor-field" data-tou-editor-field="${field}">
      <label>${this.touFieldLabel(field)}</label><div>${control}</div>
      <div class="hint tou-field-state"><span>Aktualna wartość: <strong>${this.formatTouFieldValue(field, data.actual)}</strong></span>${expected}<span>Status: <strong>${this.touStatusLabel(data.status)}</strong></span></div>
    </div>`;
  }

  renderTouReverseSyncSummary() {
    const reverse = this.touReverseSyncDiagnostics();
    const changed = Array.isArray(reverse.reverse_sync_changed_hours)
      ? reverse.reverse_sync_changed_hours.join(", ")
      : "";
    const roundTrip = reverse.reverse_sync_round_trip_ok === true
      ? "Zgodny"
      : reverse.reverse_sync_round_trip_ok === false ? "Niezgodny" : "Brak danych";
    const error = reverse.reverse_sync_last_error && reverse.reverse_sync_last_error !== "none"
      ? `<div class="bad">${this.escapeHtml(String(reverse.reverse_sync_last_error))}</div>`
      : "";
    return `<div class="hint tou-reverse-sync" data-tou-reverse-sync>
      <div>Synchronizacja Harmonogramu: <strong>${this.touReverseStatusLabel(reverse.reverse_sync_status)}</strong></div>
      <div>Zmienione godziny: <strong>${changed || "Brak"}</strong></div>
      <div>Round-trip: <strong>${roundTrip}</strong></div>${error}
    </div>`;
  }

  renderTouSettingsContent() {
    const capabilityRows = this.touCapabilitiesDiagnostics();
    const supportedFields = this.touFieldNames().filter((field) => capabilityRows.some((row) => row.fields?.[field]?.supported === true));
    if (!supportedFields.length) {
      return `<div class="hint">Brak dostępnych pól Deye Time Of Use dla tego providera.</div>${this.renderTouReverseSyncSummary()}`;
    }
    const headers = supportedFields.map((field) => `<th>${this.touFieldLabel(field)}</th>`).join("");
    const rows = capabilityRows.map((capability) => {
      const slot = Number(capability.slot_index);
      const cells = supportedFields.map((field) => {
        const data = this.touFieldDiagnostics(slot, field);
        return `<td>${data.capability.supported === true ? this.formatTouFieldValue(field, data.actual) : "—"}</td>`;
      }).join("");
      const hasReadable = supportedFields.some((field) => capability.fields?.[field]?.readable === true || capability.fields?.[field]?.current_available === false);
      const action = hasReadable
        ? `<button class="icon-only" data-open-tou="${slot}" title="${capability.read_only === true ? "Pokaż fizyczny slot" : "Edytuj fizyczny slot"}">${this.iconSvg(capability.read_only === true ? "info" : "edit")}</button>`
        : "Brak odczytu";
      return `<tr><td>${slot}</td>${cells}<td>${action}</td></tr>`;
    }).join("");
    const readOnly = capabilityRows.length > 0 && capabilityRows.every((row) => row.read_only === true);
    const blocked = capabilityRows.some((row) => this.touControlBlocked(row));
    const pending = this.touWritePending();
    const note = readOnly
      ? "Ten provider udostępnia Deye Time Of Use tylko do odczytu."
      : blocked
        ? "Sterowanie Deye jest wyłączone."
        : pending ? "Trwa zapis Deye Time Of Use" : "Pola są renderowane zgodnie z capabilities przekazanymi przez backend.";
    return `<div class="hint">${note}</div>
      <div class="hint">Status operacji: <strong>${this.touOperationStatusLabel()}</strong></div>
      <table class="settings-table" data-tou-capabilities-table><thead><tr><th>Slot</th>${headers}<th>Akcja</th></tr></thead><tbody>${rows}</tbody></table>
      ${this.renderTouReverseSyncSummary()}`;
  }

  resetBulkEditState() {
    this._bulkEditDraft = null;
    this._bulkEditFields = null;
  }

  updateBulkApplyState() {
    this.querySelectorAll("[data-apply-multi]").forEach((button) => {
      button.disabled = this._bulkApplying || !this._selectedSlots?.size;
      button.setAttribute("aria-busy", this._bulkApplying ? "true" : "false");
    });
  }

  async applyMultiEdit(slots) {
    if (this._bulkApplying) return false;
    const selected = this.selectedSlotList(slots);
    if (!selected.length) return false;
    const form = this.collectBulkEditState();
    if (!form) return false;
    const checked = (name) => Boolean(form.fields[name]);
    const activeValue = form.values.active === "on";
    const mode = this.normalizeManagerMode(form.values.mode);
    const sellPower = form.values.sellPower;
    const dischargeCurrent = form.values.dischargeCurrent;
    const chargeCurrent = form.values.chargeCurrent;
    const minSoc = form.values.minSoc;
    const minSellPrice = form.values.minSellPrice;

    const updates = selected.map(([key]) => {
      const update = { slot_key: key };
      if (checked("sellPower")) update.sell_power = sellPower;
      if (checked("dischargeCurrent")) update.discharge_current = dischargeCurrent;
      if (checked("chargeCurrent")) update.charge_current = chargeCurrent;
      if (checked("minSoc")) update.minimum_sell_soc = minSoc;
      if (checked("minSellPrice")) update.min_sell_price = minSellPrice;
      if (checked("mode")) update.mode = mode;
      if (checked("active")) update.enabled = activeValue;
      return update;
    });
    this._bulkApplying = true;
    this.updateBulkApplyState();
    if (!await this.applySchedulePatch(updates)) {
      this._bulkApplying = false;
      this.updateBulkApplyState();
      return false;
    }
    this._bulkApplying = false;
    this.resetBulkEditState();
    this._dialog = null;
    this.captureScrollPositions();
    this.render();
    return true;
  }

  timeInput(entityId) {
    const raw = this.state(entityId, "00:00:00");
    const value = raw.length >= 5 ? raw.slice(0, 5) : raw;
    return `<input class="time-input" data-time="${entityId}" type="time" value="${value}" ${this.exists(entityId) ? "" : "disabled"}>`;
  }

  stat(label, value, cls = "", liveKey = "", icon = "") {
    const liveCard = liveKey ? ` data-live-card="${liveKey}"` : "";
    const liveValue = liveKey ? ` data-live="${liveKey}"` : "";
    return `<div class="stat ${cls}"${liveCard}>${icon ? `<i class="stat-icon">${this.iconSvg(icon)}</i>` : ""}<div class="stat-copy"><span>${label}</span><strong${liveValue}>${value}</strong></div></div>`;
  }

  row(label, value, cls = "") {
    return `<div class="row ${cls}"><span>${label}</span><strong>${value}</strong></div>`;
  }

  readMode(rawStatus) {
    const status = String(rawStatus || "").toUpperCase();
    if (status.includes("SELL BLOCKED")) return ["Sprzedaż zatrzymana", "warn"];
    if (status.includes("GRID CHARGE")) return ["Ładowanie z sieci według harmonogramu", "charge"];
    if (status.includes("PV CHARGE")) return ["Ładowanie z PV według harmonogramu", "charge"];
    if (status.includes("EMERGENCY")) return ["Awaryjnie zatrzymany", "bad"];
    if (status.includes("MAPPING ERROR")) return ["Błąd mapowania Deye", "bad"];
    if (status.includes("SCHEDULE APPLY ERROR")) return ["Nie zastosowano bie\u017c\u0105cego slotu", "bad"];
    if (status.includes("NO DATA")) return ["Brak danych sterowania", "warn"];
    if (status.includes("DEFAULT")) return ["Ustawienia domyślne", "warn"];
    if (status.includes("PROTECT")) return ["Ochrona baterii", "warn"];
    if (status.includes("SCHEDULER OFF")) return ["Harmonogram wy\u0142\u0105czony", "neutral"];
    if (status.includes("SLOT DISABLED")) return ["Slot wy\u0142\u0105czony - domy\u015blne", "warn"];
    if (status.includes("GRID CHARGE")) return ["\u0141adowanie z sieci", "charge"];
    if (status.includes("SELLING ACTIVE")) return ["Sprzeda\u017c wed\u0142ug harmonogramu", "good"];
    if (status.includes("ZERO EXPORT CT")) return ["Normalna Praca", "ct"];
    if (status.includes("ZERO EXPORT LOAD")) return ["Normalna Praca", "zero"];
    if (status.includes("SCHEDULE")) return ["Harmonogram aktywny", "good"];
    if (status.includes("MANUAL")) return ["Sprzeda\u017c r\u0119czna", "good"];
    if (status.includes("CHARGE")) return ["\u0141adowanie r\u0119czne", "charge"];
    if (status.includes("STOP")) return ["Zatrzymany - ustawienia domy\u015blne", "bad"];
    if (status.includes("SOC")) return ["Sprzeda\u017c zablokowana przez SOC", "warn"];
    if (status.includes("PRICE")) return ["Sprzeda\u017c zablokowana przez cen\u0119", "warn"];
    if (status.includes("WAITING")) return ["Oczekiwanie na decyzję", "neutral"];
    if (status.includes("IDLE")) return ["Bezczynny", ""];
    if (!rawStatus || rawStatus === "brak") return ["Brak danych", "warn"];
    return [rawStatus, ""];
  }

  formatAppliedAt(value) {
    if (!value || value === "brak" || value === "never") return "Jeszcze nie zastosowano";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("pl-PL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  readAction(rawAction) {
    const action = String(rawAction || "");
    const upper = action.toUpperCase();
    if (!action || action === "brak" || upper === "IDLE") return "Brak ostatniej akcji";
    if (upper.includes("INACTIVE SLOT")) return "Ustawienia domy\u015blne - slot wy\u0142\u0105czony";
    if (upper.includes("PRICE GUARD")) return "Ustawienia domy\u015blne - blokada ceny";
    if (upper.includes("DEFAULTS RESTORED")) return "Przywr\u00f3cono ustawienia domy\u015blne";
    if (upper.includes("EMERGENCY")) return "Wykonano zatrzymanie awaryjne";
    if (upper.includes("BLOCKED BY GUARD")) return "Sterowanie zablokowane przez ochron\u0119";
    if (upper.includes("CHARGE BLOCKED")) return "\u0141adowanie zablokowane";
    if (upper.includes("APPLIED SCHEDULE")) return "Zastosowano bie\u017c\u0105cy slot harmonogramu";
    if (upper.includes("APPLIED MANUAL SELL")) return "Zastosowano sprzeda\u017c r\u0119czn\u0105";
    if (upper.includes("APPLIED CHARGE BATTERY")) return "Zastosowano \u0142adowanie baterii";
    return action;
  }

  gridFlow(value) {
    const power = this.asNumber(value);
    if (power === null) return "Brak danych";
    if (power < -1) return `Oddawanie ${Math.abs(power).toFixed(0)} W`;
    if (power > 1) return `Pobór ${power.toFixed(0)} W`;
    return "Bilans 0 W";
  }

  batteryFlow(value) {
    const power = this.asNumber(value);
    if (power === null) return "Brak danych";
    if (power < -1) return `\u0141adowanie ${Math.abs(power).toFixed(0)} W`;
    if (power > 1) return `Roz\u0142adowanie ${power.toFixed(0)} W`;
    return "Spoczynek 0 W";
  }

  flowGeometry({
    tileWidth = 300,
    tileGap = 28,
    inverterColumnWidth = 640,
    inverterVisualWidth = 190,
  } = {}) {
    const boardHeight = 600;
    const boardWidth = tileWidth * 2 + inverterColumnWidth + tileGap * 2;
    const inverterCenterX = tileWidth + tileGap + inverterColumnWidth / 2;
    const inverterVisualHeight = inverterVisualWidth * (250 / 190);
    const inverterCenterY = boardHeight / 2;
    const inverterPortOffsetY = inverterVisualHeight * 0.22;
    const tileTopY = 145;
    const tileBottomY = boardHeight - tileTopY;
    const points = {
      pvTile: { x: tileWidth, y: tileTopY },
      gridTile: { x: tileWidth, y: tileBottomY },
      batteryTile: { x: boardWidth - tileWidth, y: tileTopY },
      homeTile: { x: boardWidth - tileWidth, y: tileBottomY },
      pvPort: { x: inverterCenterX - inverterVisualWidth / 2, y: inverterCenterY - inverterPortOffsetY },
      gridPort: { x: inverterCenterX - inverterVisualWidth / 2, y: inverterCenterY + inverterPortOffsetY },
      batteryPort: { x: inverterCenterX + inverterVisualWidth / 2, y: inverterCenterY - inverterPortOffsetY },
      homePort: { x: inverterCenterX + inverterVisualWidth / 2, y: inverterCenterY + inverterPortOffsetY },
    };
    const coordinate = (value) => Number(value.toFixed(2));
    const curve = (start, end) => {
      const controlOffset = (end.x - start.x) * 0.45;
      return `M${coordinate(start.x)},${coordinate(start.y)} C${coordinate(start.x + controlOffset)},${coordinate(start.y)} ${coordinate(end.x - controlOffset)},${coordinate(end.y)} ${coordinate(end.x)},${coordinate(end.y)}`;
    };
    return {
      boardWidth,
      boardHeight,
      points,
      paths: {
        pvToInverter: curve(points.pvTile, points.pvPort),
        batteryToInverter: curve(points.batteryTile, points.batteryPort),
        inverterToBattery: curve(points.batteryPort, points.batteryTile),
        gridToInverter: curve(points.gridTile, points.gridPort),
        inverterToGrid: curve(points.gridPort, points.gridTile),
        inverterToHome: curve(points.homePort, points.homeTile),
      },
    };
  }

  energyFlowPanel() {
    const [modeText, modeClass] = this.readMode(this.state(this.entity("sensor", "manager_status")));
    const activeSlot = this.state(this.entity("sensor", "active_slot"), "");
    const activeSlotLabel = (this.scheduleSlots().find(([key]) => key === activeSlot)?.[1] || activeSlot).replace(/:00/g, "");
    const currentMode = this.deyeWorkModeState();
    const currentModeMeta = currentMode ? this.modeMeta(currentMode, true) : { cls: "disabled" };
    const managerModeClass = this.modeTextClass(modeText);
    const control = this.controlState();
    const controlOn = control.enabled;
    const controlStatus = control.status;
    const statusAttrs = this.managerStatusAttributes();
    const plannedAction = this.state(this.entity("sensor", "planned_manager_action"), statusAttrs.planned_manager_action || "—");
    const executedAction = this.state(this.entity("sensor", "executed_manager_action"), statusAttrs.executed_manager_action || "—");
    const layout = this.effectiveLayout();
    const tileWidth = layout.energy_tile_width;
    const tileGap = layout.energy_tile_gap;
    const inverterScale = layout.inverter_scale;
    const flowSpeed = layout.flow_animation_speed;
    const inverterColumnWidth = Math.round(640 * inverterScale);
    const inverterVisualWidth = Math.round(190 * inverterScale);
    const geometry = this.flowGeometry({ tileWidth, tileGap, inverterColumnWidth, inverterVisualWidth });
    const boardWidth = geometry.boardWidth;
    const panelWidth = boardWidth + 32;
    const panelHeight = geometry.boardHeight + 168;
    const tilePadding = tileWidth < 150 ? 8 : tileWidth < 210 ? 12 : 17;
    const tileIconSize = tileWidth < 150 ? 34 : tileWidth < 210 ? 46 : 60;
    const tileContentGap = tileWidth < 150 ? 7 : tileWidth < 210 ? 9 : 13;
    const compactStatus = boardWidth < 900;
    const statusIconSize = compactStatus ? 36 : 56;
    const statusGap = compactStatus ? 8 : 15;
    const statusPadY = compactStatus ? 10 : 15;
    const statusPadX = compactStatus ? 9 : 19;
    const flowDuration = Math.max(0.5, 18 / flowSpeed).toFixed(2);
    const flowOffset = Math.round(220 * flowDuration / 3);

    const st = (key, fallback = null) => this.asNumber(this.state(this.entity("sensor", key)), fallback);
    const pvPower = st("pv_power", 0) || 0;
    const pvDaily = st("daily_pv_production", 0) || 0;
    const pv1Power = st("pv1_power");
    const pv1V = st("pv1_voltage");
    const pv1A = st("pv1_current");
    const pv2Power = st("pv2_power");
    const pv2V = st("pv2_voltage");
    const pv2A = st("pv2_current");

    const gridPower = st("grid_power", 0) || 0;
    const gridL1Power = st("grid_l1_power");
    const gridL1V = st("grid_l1_voltage");
    const gridL2Power = st("grid_l2_power");
    const gridL2V = st("grid_l2_voltage");
    const gridL3Power = st("grid_l3_power");
    const gridL3V = st("grid_l3_voltage");
    const gridBought = st("daily_energy_bought");
    const gridSold = st("daily_energy_sold");
    const frequency = st("load_frequency");

    const batteryPower = st("battery_power", 0) || 0;
    const batterySoc = this.optionalSocNumber(
      this.state(this.entity("sensor", "battery_soc")),
    );
    const batteryVoltage = st("battery_bms_voltage");
    const batteryCurrent = st("battery_current");
    const batteryTemp = st("battery_temperature");
    const batteryChargeDaily = st("daily_battery_charge");
    const batteryDischargeDaily = st("daily_battery_discharge");

    const loadPower = st("load_power", 0) || 0;
    const loadDaily = st("daily_load_consumption");
    const loadL1Power = st("load_l1_power");
    const loadL2Power = st("load_l2_power");
    const loadL3Power = st("load_l3_power");
    const inverterTemp = st("inverter_ac_temperature");
    const soldTodayKwh = this.asNumber(this.state(this.entity("sensor", "sold_energy_today")), 0) || 0;
    const soldTodayPln = this.asNumber(this.state(this.entity("sensor", "sold_value_today")), 0) || 0;

    const active = {
      pv: pvPower > 1,
      gridImport: gridPower > 1,
      gridExport: gridPower < -1,
      batteryDischarge: batteryPower > 1,
      batteryCharge: batteryPower < -1,
      load: loadPower > 1,
    };

    const fmtPower = (v) => (v === null || v === undefined || Number.isNaN(v)) ? "—" : this.formatPower(v);
    const fmtNumber = (v, digits = 2) => (v === null || v === undefined || Number.isNaN(v)) ? "—" : v.toFixed(digits);

    const gridMain = gridPower < -1 ? `Eksport ${fmtPower(Math.abs(gridPower))}` : gridPower > 1 ? `Pobór ${fmtPower(gridPower)}` : `Bilans 0 W`;
    const batteryDirection = batteryPower < -1 ? `Ładowanie ${fmtPower(Math.abs(batteryPower))}` : batteryPower > 1 ? `Rozładowanie ${fmtPower(batteryPower)}` : `Spoczynek`;
    const socMain = batterySoc === null ? "—" : `${Math.round(batterySoc)}`;

    const phaseRow = (label, power, volt) => `
      <div class="flow-phase">
        <div class="flow-phase-label">${label}</div>
        <div class="flow-phase-power">${power}</div>
        <div class="flow-phase-volt">${volt}</div>
      </div>`;

    const pvPath = geometry.paths.pvToInverter;
    const batPath = active.batteryCharge
      ? geometry.paths.inverterToBattery
      : geometry.paths.batteryToInverter;
    const gridPath = active.gridExport
      ? geometry.paths.inverterToGrid
      : geometry.paths.gridToInverter;
    const homePath = geometry.paths.inverterToHome;

    const lineClass = (isActive) => isActive ? "flow-line flow-active" : "flow-line";
    const flowMarker = (key, isActive) => isActive ? ` marker-end="url(#flow-arrow-${key})"` : "";

    const inverterSvg = `<svg class="flow-inverter-svg" viewBox="0 0 190 250" xmlns="http://www.w3.org/2000/svg" aria-label="Falownik Deye">
      <defs>
        <linearGradient id="invBody23" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#f8fbff"/>
          <stop offset="0.52" stop-color="#e5edf7"/>
          <stop offset="1" stop-color="#b8c7da"/>
        </linearGradient>
        <linearGradient id="invEdge23" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#e9f8ff"/>
          <stop offset="1" stop-color="#93a9c0"/>
        </linearGradient>
        <radialGradient id="invScreen23" cx="50%" cy="25%" r="85%">
          <stop offset="0" stop-color="#16243b"/>
          <stop offset="1" stop-color="#07101f"/>
        </radialGradient>
        <filter id="invShadow23" x="-35%" y="-25%" width="170%" height="175%">
          <feDropShadow dx="0" dy="8" stdDeviation="9" flood-color="#000" flood-opacity="0.5"/>
          <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="#19b9ff" flood-opacity="0.55"/>
        </filter>
      </defs>
      <rect x="11" y="7" width="168" height="230" rx="23" fill="url(#invBody23)" stroke="#36c4ff" stroke-width="3" filter="url(#invShadow23)"/>
      <path d="M31 15h128c7 0 12 5 12 12v183c0 9-7 17-16 18H35c-9-1-16-9-16-18V27c0-7 5-12 12-12Z" fill="none" stroke="url(#invEdge23)" stroke-width="2" opacity=".7"/>
      <rect x="34" y="34" width="122" height="67" rx="7" fill="url(#invScreen23)" stroke="#0b1a2d" stroke-width="2"/>
      <path d="M43 42h104" stroke="#263a53" stroke-width="1" opacity=".7"/>
      <circle cx="55" cy="51" r="5" fill="#3cff91" stroke="#d8ffe9" stroke-width="2"/>
      <circle cx="72" cy="51" r="5" fill="#3cff91" stroke="#d8ffe9" stroke-width="2"/>
      <circle cx="89" cy="51" r="5" fill="#3cff91" stroke="#d8ffe9" stroke-width="2"/>
      <circle cx="55" cy="51" r="10" fill="none" stroke="#3cff91" stroke-width="1" opacity=".22"/>
      <rect x="76" y="184" width="38" height="20" rx="4" fill="#18b8f2" stroke="#e6f8ff" stroke-width="2"/>
      <path d="M80 187h30" stroke="#62dcff" stroke-width="2" opacity=".85"/>
      <path d="M59 219h72" stroke="#8da0b5" stroke-width="2" opacity=".55"/>
    </svg>`;

    return `
      <section class="panel status-panel">
        <h2 class="panel-title">${this.iconSvg("chart")} Status energii</h2>
        <style>
.status-panel{background:radial-gradient(circle at 50% 42%,rgba(13,72,113,.13),transparent 34%),radial-gradient(circle at 12% 0%,rgba(20,85,130,.2),transparent 31%),linear-gradient(180deg,#030d17 0%,#061521 100%)!important;border-color:rgba(85,145,177,.48)!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.035),0 16px 38px rgba(0,0,0,.27)!important}
.status-panel>.panel-title{padding:18px 22px!important;font-size:27px!important;gap:12px!important;letter-spacing:-.35px}
.status-panel>.panel-title svg{width:27px!important;height:27px!important;filter:drop-shadow(0 0 7px rgba(21,155,255,.55))}
.flow-wrapper{max-width:${panelWidth}px;margin:0 auto;overflow:hidden;position:relative}
.flow-scaler{width:${panelWidth}px;transform-origin:top left;transform:scale(1);line-height:1}
.energy-flow-panel{width:${panelWidth}px;height:${panelHeight}px;padding:16px;box-sizing:border-box;position:relative}
.flow-board{position:relative;display:grid;grid-template-columns:${tileWidth}px ${inverterColumnWidth}px ${tileWidth}px;grid-template-rows:${geometry.boardHeight}px;gap:0 ${tileGap}px;align-items:center;justify-items:center;width:${boardWidth}px;height:${geometry.boardHeight}px}
.flow-tile{position:relative;z-index:3;width:${tileWidth}px;height:290px;border:1.5px solid rgba(86,149,184,.48);border-radius:14px;background:radial-gradient(circle at 22% 0%,rgba(26,100,151,.13),transparent 38%),linear-gradient(180deg,rgba(6,21,34,.985),rgba(4,16,26,.99));padding:16px ${tilePadding}px;box-shadow:inset 0 1px 0 rgba(255,255,255,.035),0 12px 26px rgba(0,0,0,.3),0 0 18px rgba(16,91,138,.06);box-sizing:border-box;overflow:hidden}
          .flow-tile-pv{grid-column:1;grid-row:1;justify-self:start;align-self:start}
          .flow-tile-grid{grid-column:1;grid-row:1;justify-self:start;align-self:end}
          .flow-tile-battery{grid-column:3;grid-row:1;justify-self:end;align-self:start}
          .flow-tile-home{grid-column:3;grid-row:1;justify-self:end;align-self:end}
.flow-inverter{grid-column:2;grid-row:1;align-self:center;justify-self:center;text-align:center;position:relative;z-index:3;min-width:240px}
.flow-tile-head{display:flex;align-items:flex-start;gap:${tileContentGap}px;margin-bottom:10px}
.flow-tile-heading{min-width:0;flex:1;padding-top:2px}
.flow-tile-icon{width:${tileIconSize + 2}px;height:${tileIconSize + 2}px;flex:0 0 auto;display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 0 8px currentColor)}
.flow-tile-icon svg{width:${tileIconSize}px;height:${tileIconSize}px;overflow:visible}
.flow-tile-title{font-size:${tileWidth < 150 ? 12 : 15}px;font-weight:800;color:#f3f8fc;white-space:${tileWidth < 190 ? "normal" : "nowrap"};line-height:1.2;text-shadow:0 1px 4px rgba(0,0,0,.65)}
.flow-tile-main{font-size:${tileWidth < 150 ? 19 : tileWidth < 210 ? 23 : 27}px;font-weight:900;line-height:1.05;margin:8px 0 5px;letter-spacing:-.45px;text-shadow:0 0 10px currentColor;overflow-wrap:anywhere}
.flow-tile-main .unit{font-size:15px;font-weight:700;color:#c7d7e1;margin-left:4px;text-shadow:none}
.flow-tile-sub{font-size:13px;color:#b7c9d5;line-height:1.28}
.flow-tile-divider{border:0;border-top:1px solid rgba(95,148,177,.38);margin:12px 0}
.flow-detail-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;text-align:center}
          .flow-detail-row.three-cols{grid-template-columns:repeat(3,1fr)}
.flow-phase+.flow-phase{border-left:1px solid rgba(93,145,174,.34)}
.flow-phase-label{font-size:12px;color:#a9c1d0;letter-spacing:.2px;margin-bottom:7px}
.flow-phase-power{font-size:15px;font-weight:850;color:#f2f8fc;line-height:1.15}
.flow-phase-volt{font-size:12px;color:#b7c7d2;margin-top:6px;line-height:1.2;white-space:nowrap}
          .flow-tile-pv .flow-tile-main{color:#fbbf24}
          .flow-tile-grid .flow-tile-main{color:#c084fc}
          .flow-tile-battery .flow-tile-main{color:#4ade80}
          .flow-tile-home .flow-tile-main{color:#38bdf8}
          .flow-tile .positive{color:#4ade80}
          .flow-tile .sold{color:#4ade80}
          .flow-tile .bought{color:#c084fc}
.flow-tile-foot{font-size:12px;color:#b4c6d1;line-height:1.65}
.flow-inverter-svg{width:${inverterVisualWidth}px;height:auto;display:block;margin:0 auto}
.flow-inverter-name{font-size:17px;font-weight:850;color:#f2f7fb;margin-top:7px;text-shadow:0 2px 6px rgba(0,0,0,.8)}
.flow-inverter-temp{display:flex;align-items:center;justify-content:center;gap:5px;font-size:16px;font-weight:800;color:#23b9ff;margin-top:7px;text-shadow:0 0 8px rgba(35,185,255,.48)}
.flow-inverter-temp svg{width:18px;height:18px}
.flow-sold-tile{display:grid;grid-template-columns:38px 1fr;gap:10px;align-items:center;padding:8px 14px;margin:14px auto 0;border:1px solid rgba(89,151,181,.4);border-radius:11px;background:linear-gradient(180deg,rgba(7,24,35,.96),rgba(4,15,24,.98));min-width:260px;box-shadow:0 8px 18px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.025)}
.flow-sold-icon{width:34px;height:34px;display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 0 6px rgba(126,226,45,.5))}
.flow-sold-icon svg{width:30px;height:30px}
          .flow-sold-copy{text-align:left;min-width:0}
.flow-sold-copy span{display:block;font-size:11px;color:#8fb0c3;text-transform:uppercase;letter-spacing:.45px;line-height:1.1}
.flow-sold-value{display:block;font-size:16px;font-weight:850;color:#f2f8fc;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.flow-svg{position:absolute;top:0;left:0;width:100%;height:100%;z-index:1;overflow:visible;pointer-events:none}
.flow-line{fill:none;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:none;filter:url(#flowGlow23)}
.flow-line-bg{fill:none;stroke-linecap:round;stroke-width:5;opacity:.34;filter:url(#flowGlowSoft23)}
.flow-active{stroke-dasharray:1 22;stroke-width:7!important;animation:flowDash ${flowDuration}s linear infinite}
          @keyframes flowDash{to{stroke-dashoffset:-${flowOffset}}}
.flow-daily-summary{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px 10px;font-size:12px;line-height:1.3}
.flow-daily-summary>span{color:#b4c6d1}
.flow-daily-summary strong{font-size:14px;font-weight:850;white-space:nowrap}
.flow-daily-pv strong{color:#fbbf24}
.flow-daily-home strong{color:#38bdf8}
.flow-bottom{display:grid;grid-template-columns:repeat(4,1fr);gap:0;width:${boardWidth}px;margin-top:9px;border:1px solid rgba(84,148,181,.46);border-radius:13px;background:linear-gradient(180deg,rgba(6,21,33,.97),rgba(4,15,24,.99));overflow:hidden;box-shadow:0 12px 26px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.03)}
.flow-status-tile{display:flex;align-items:center;gap:${statusGap}px;padding:${statusPadY}px ${statusPadX}px;min-height:116px;box-sizing:border-box;border-right:1px solid rgba(89,146,174,.35)}
          .flow-status-tile:last-child{border-right:0}
.flow-status-icon{width:${statusIconSize}px;height:${statusIconSize}px;flex:0 0 auto;display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 0 8px currentColor)}
.flow-status-icon svg{width:${statusIconSize - 5}px;height:${statusIconSize - 5}px;stroke-width:1.8}
          .flow-status-copy{min-width:0;flex:1}
.flow-status-copy span{display:block;font-size:${compactStatus ? 10 : 14}px;font-weight:800;color:#f1f7fb;letter-spacing:0}
.flow-status-copy strong{display:block;font-size:${compactStatus ? 12 : 17}px;font-weight:850;margin-top:${compactStatus ? 5 : 8}px;white-space:normal;overflow-wrap:anywhere;line-height:1.18}
.flow-status-copy .sub{font-size:${compactStatus ? 9 : 13}px;color:#aebfca;margin-top:${compactStatus ? 4 : 6}px;line-height:1.25;text-transform:none}
.flow-status-copy .slot-time{color:#fbbf24;font-size:${compactStatus ? 14 : 20}px;text-shadow:0 0 9px rgba(251,191,36,.35)}
          .mode-selling{color:#7ee22d}
          .mode-normal{color:#4ade80}
          .mode-charge{color:#f6a619}
          .mode-disabled{color:#b9c9d4}
.mode-zero,.mode-ct{color:#38bdf8}
.flow-footer{text-align:center;width:${boardWidth}px;margin-top:12px;font-size:13px;color:#89a6b7}
            .ai-crisp-main{min-width:0;border:1px solid rgba(105,159,184,.25);border-radius:7px;overflow:hidden;background:rgba(3,18,28,.38)}
            .ai-crisp-integrated-grid{min-width:0;border-top:1px solid rgba(104,151,174,.2);background:rgba(3,17,27,.28)}
            .ai-crisp-plot,.ai-crisp-axis{height:clamp(236px,22vw,268px)}
            .ai-crisp-axis{position:relative;align-self:start;display:block;min-height:0;color:#a9c3d0;font-size:11px;font-weight:700}
            .ai-crisp-axis b{position:absolute;top:-21px;color:#e3f2f7;font-size:12px}
            .ai-crisp-axis-left b{right:0}.ai-crisp-axis-right b{left:0}
            .ai-crisp-axis-values{height:100%;display:flex;flex-direction:column;justify-content:space-between}
            .ai-crisp-axis-left .ai-crisp-axis-values{align-items:flex-end}.ai-crisp-axis-right .ai-crisp-axis-values{align-items:flex-start}
            .ai-crisp-now-tag{right:auto;transform:translateX(-50%);white-space:nowrap}
            .ai-crisp-weather-grid,.ai-crisp-status,.ai-crisp-time-grid{width:100%;max-width:100%;min-width:0;box-sizing:border-box}
            .ai-crisp-weather-grid{border-top:0}
            .ai-crisp-weather-cell,.ai-crisp-status>div span,.ai-crisp-time-grid span{border-left:1px solid rgba(104,151,174,.12)}
            .ai-crisp-weather-cell:first-child,.ai-crisp-status>div span:first-child,.ai-crisp-time-grid span:first-child{border-left:0}
            .ai-crisp-status{display:grid;grid-template-columns:minmax(0,1fr);gap:3px;margin:0;padding:5px 0;border-top:1px solid rgba(104,151,174,.18)}
            .ai-crisp-status>div{display:grid;grid-template-columns:repeat(24,minmax(0,1fr));gap:2px;height:12px}
            .ai-crisp-status>div span{display:block;min-width:0;border-radius:2px}
            .ai-crisp-status>div.sell span{background:rgba(105,212,56,.09)}
            .ai-crisp-status>div.charge span{background:rgba(53,174,232,.08)}
            .ai-crisp-status>div.tariff span{background:rgba(199,173,91,.1)}
            .ai-crisp-status>div span.active.sell{background:#69d438;box-shadow:0 0 0 1px rgba(141,233,96,.55) inset}
            .ai-crisp-status>div span.active.charge{background:#35aee8;box-shadow:0 0 0 1px rgba(112,205,250,.55) inset}
            .ai-crisp-status>div span.active.tariff{background:#9f863d;box-shadow:0 0 0 1px rgba(199,173,91,.55) inset}
            .ai-crisp-time-grid{margin:0;min-height:25px;padding-top:6px;border-top:1px solid rgba(104,151,174,.18)}
            .ai-crisp-legend .sell i{background:#69d438}.ai-crisp-legend .charge i{background:#35aee8}.ai-crisp-legend .tariff i{background:#9f863d}
           </style>
        <div class="flow-wrapper">
          <div class="flow-scaler" data-base-width="${panelWidth}" data-base-height="${panelHeight}" data-tile-width="${tileWidth}" data-tile-gap="${tileGap}" data-inverter-column-width="${inverterColumnWidth}" data-inverter-visual-width="${inverterVisualWidth}">
            <div class="energy-flow-panel">
              <div class="flow-board">
                <div class="flow-tile flow-tile-pv">
                  <div class="flow-tile-head">
                    <div class="flow-tile-icon" style="color:#fbbf24">${this.iconSvg("pv2")}</div>
                    <div class="flow-tile-heading">
                      <div class="flow-tile-title">PV (Produkcja)</div>
                      <div class="flow-tile-main" data-live="pv-main">${fmtPower(pvPower)}</div>
                    </div>
                  </div>
                  <hr class="flow-tile-divider">
                  <div class="flow-detail-row">
                    ${phaseRow("PV1", `<span style="color:#fbbf24" data-live="pv1-power">${fmtPower(pv1Power)}</span>`, `<span data-live="pv1-volts">${fmtNumber(pv1V, 1)}</span> V | <span data-live="pv1-amps">${fmtNumber(pv1A, 1)}</span> A`)}
                    ${phaseRow("PV2", `<span style="color:#fbbf24" data-live="pv2-power">${fmtPower(pv2Power)}</span>`, `<span data-live="pv2-volts">${fmtNumber(pv2V, 1)}</span> V | <span data-live="pv2-amps">${fmtNumber(pv2A, 1)}</span> A`)}
                  </div>
                  <hr class="flow-tile-divider">
                  <div class="flow-daily-summary flow-daily-pv">
                    <span>Wyprodukowano dzisiaj:</span>
                    <strong><span data-live="pv-daily">${fmtNumber(pvDaily, 2)}</span> kWh</strong>
                  </div>
                </div>
                <div class="flow-tile flow-tile-grid">
                  <div class="flow-tile-head">
                    <div class="flow-tile-icon" style="color:#c084fc">${this.iconSvg("grid2")}</div>
                    <div class="flow-tile-heading">
                      <div class="flow-tile-title">Sieć</div>
                      <div class="flow-tile-main" data-live="grid-main">${gridMain}</div>
                    </div>
                  </div>
                  <hr class="flow-tile-divider">
                  <div class="flow-detail-row three-cols">
                    ${phaseRow("L1", `<span style="color:#c084fc" data-live="grid-l1-power">${fmtPower(gridL1Power)}</span>`, `<span data-live="grid-l1-volt">${fmtNumber(gridL1V, 1)}</span> V`)}
                    ${phaseRow("L2", `<span style="color:#c084fc" data-live="grid-l2-power">${fmtPower(gridL2Power)}</span>`, `<span data-live="grid-l2-volt">${fmtNumber(gridL2V, 1)}</span> V`)}
                    ${phaseRow("L3", `<span style="color:#c084fc" data-live="grid-l3-power">${fmtPower(gridL3Power)}</span>`, `<span data-live="grid-l3-volt">${fmtNumber(gridL3V, 1)}</span> V`)}
                  </div>
                  <hr class="flow-tile-divider">
                  <div class="flow-tile-foot">
                    <div>Dzisiaj: <span class="bought">pobrano <span data-live="grid-bought">${fmtNumber(gridBought, 2)}</span> kWh</span></div>
                    <div>Dzisiaj: <span class="sold">oddano <span data-live="grid-sold">${fmtNumber(gridSold, 2)}</span> kWh</span></div>
                    <div>Częstotliwość: <span data-live="grid-frequency">${fmtNumber(frequency, 2)}</span> Hz</div>
                  </div>
                </div>
                <div class="flow-inverter">
                  ${inverterSvg}
                  <div class="flow-inverter-name">Falownik Deye</div>
                  <div class="flow-inverter-temp">${this.iconSvg("thermometer")}<span data-live="inverter-temp">${inverterTemp === null ? "—" : `${Math.round(inverterTemp)}`}</span> °C</div>
                  <div class="flow-sold-tile">
                    <div class="flow-sold-icon" style="color:#7ee22d">${this.iconSvg("money")}</div>
                    <div class="flow-sold-copy">
                      <span>Sprzedano dzisiaj</span>
                      <strong class="flow-sold-value" data-live="sold-today-line">${fmtNumber(soldTodayKwh, 2)} kWh / ${fmtNumber(soldTodayPln, 2)} PLN</strong>
                    </div>
                  </div>
                </div>
                <div class="flow-tile flow-tile-battery">
                  <div class="flow-tile-head">
                    <div class="flow-tile-icon" style="color:#4ade80">${this.iconSvg("battery2")}</div>
                    <div class="flow-tile-heading">
                      <div class="flow-tile-title">Bateria</div>
                      <div class="flow-tile-main"><span class="soc-value" data-live="battery-soc-value">${socMain}</span><span class="unit">% SOC</span></div>
                      <div class="flow-tile-sub" data-live="battery-direction" style="color:#4ade80">${batteryDirection}</div>
                    </div>
                  </div>
                  <hr class="flow-tile-divider">
                  <div class="flow-detail-row three-cols">
                    ${phaseRow("Napięcie", `<span data-live="battery-voltage">${fmtNumber(batteryVoltage, 1)}</span> V`, "")}
                    ${phaseRow("Prąd", `<span data-live="battery-current">${fmtNumber(batteryCurrent, 1)}</span> A`, "")}
                    ${phaseRow("Temp.", `<span data-live="battery-temp">${fmtNumber(batteryTemp, 1)}</span> °C`, "")}
                  </div>
                  <hr class="flow-tile-divider">
                  <div class="flow-tile-foot">
                    <div>Dzisiaj: <span class="positive">ładowanie <span data-live="battery-charge-daily">${fmtNumber(batteryChargeDaily, 2)}</span> kWh</span></div>
                    <div>Dzisiaj: <span class="positive">rozładowanie <span data-live="battery-discharge-daily">${fmtNumber(batteryDischargeDaily, 2)}</span> kWh</span></div>
                  </div>
                </div>
                <div class="flow-tile flow-tile-home">
                  <div class="flow-tile-head">
                    <div class="flow-tile-icon" style="color:#38bdf8">${this.iconSvg("home2")}</div>
                    <div class="flow-tile-heading">
                      <div class="flow-tile-title">Dom (Odbiorniki)</div>
                      <div class="flow-tile-main" data-live="load-main">${fmtPower(loadPower)}</div>
                    </div>
                  </div>
                  <hr class="flow-tile-divider">
                  <div class="flow-detail-row three-cols">
                    ${phaseRow("L1", `<span style="color:#38bdf8" data-live="load-l1-power">${fmtPower(loadL1Power)}</span>`, "")}
                    ${phaseRow("L2", `<span style="color:#38bdf8" data-live="load-l2-power">${fmtPower(loadL2Power)}</span>`, "")}
                    ${phaseRow("L3", `<span style="color:#38bdf8" data-live="load-l3-power">${fmtPower(loadL3Power)}</span>`, "")}
                  </div>
                  <hr class="flow-tile-divider">
                  <div class="flow-daily-summary flow-daily-home">
                    <span>Zużycie dzisiaj:</span>
                    <strong><span data-live="load-daily">${fmtNumber(loadDaily, 2)}</span> kWh</strong>
                  </div>
                </div>
                <svg class="flow-svg" viewBox="0 0 ${boardWidth} ${geometry.boardHeight}" preserveAspectRatio="xMidYMid meet">
                  <defs>
                    <filter id="flowGlow23" x="-35%" y="-35%" width="170%" height="170%">
                      <feGaussianBlur stdDeviation="2.6" result="blur"/>
                      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                    </filter>
                    <filter id="flowGlowSoft23" x="-25%" y="-25%" width="150%" height="150%">
                      <feGaussianBlur stdDeviation="2" result="blur"/>
                      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                    </filter>
                    <marker id="flow-arrow-pv" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="3.4" markerHeight="3.4" orient="auto-start-reverse"><path d="M0 0 10 5 0 10 2.7 5Z" fill="#fbbf24" stroke="none"/></marker>
                    <marker id="flow-arrow-grid" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="3.4" markerHeight="3.4" orient="auto-start-reverse"><path d="M0 0 10 5 0 10 2.7 5Z" fill="#c084fc" stroke="none"/></marker>
                    <marker id="flow-arrow-battery" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="3.4" markerHeight="3.4" orient="auto-start-reverse"><path d="M0 0 10 5 0 10 2.7 5Z" fill="#4ade80" stroke="none"/></marker>
                    <marker id="flow-arrow-home" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="3.4" markerHeight="3.4" orient="auto-start-reverse"><path d="M0 0 10 5 0 10 2.7 5Z" fill="#38bdf8" stroke="none"/></marker>
                  </defs>
                  <path data-flow-line-bg="pv" d="${pvPath}" class="flow-line-bg" stroke="#fbbf24" />
                  <path data-flow-line="pv" d="${pvPath}" stroke="#fbbf24" class="${lineClass(active.pv)}" stroke-width="4" stroke-opacity="${active.pv ? 0.96 : 0.18}"${flowMarker("pv", active.pv)} />
                  <path data-flow-line-bg="battery" d="${batPath}" class="flow-line-bg" stroke="#4ade80" />
                  <path data-flow-line="battery" d="${batPath}" stroke="#4ade80" class="${lineClass(active.batteryDischarge || active.batteryCharge)}" stroke-width="4" stroke-opacity="${active.batteryDischarge || active.batteryCharge ? 0.96 : 0.18}"${flowMarker("battery", active.batteryDischarge || active.batteryCharge)} />
                  <path data-flow-line-bg="grid" d="${gridPath}" class="flow-line-bg" stroke="#c084fc" />
                  <path data-flow-line="grid" d="${gridPath}" stroke="#c084fc" class="${lineClass(active.gridImport || active.gridExport)}" stroke-width="4" stroke-opacity="${active.gridImport || active.gridExport ? 0.96 : 0.18}"${flowMarker("grid", active.gridImport || active.gridExport)} />
                  <path data-flow-line-bg="home" d="${homePath}" class="flow-line-bg" stroke="#38bdf8" />
                  <path data-flow-line="home" d="${homePath}" stroke="#38bdf8" class="${lineClass(active.load)}" stroke-width="4" stroke-opacity="${active.load ? 0.96 : 0.18}"${flowMarker("home", active.load)} />
                </svg>
              </div>
              <div class="flow-bottom">
                <div class="flow-status-tile">
                  <div class="flow-status-icon" style="color:#4dabf7">${this.iconSvg("shield")}</div>
                  <div class="flow-status-copy">
                    <span>Sterowanie Deye</span>
                    <strong class="mode-${controlOn ? "normal" : "disabled"}" data-live="control-status">${this.escapeHtml(controlStatus)}</strong>
                    <div class="sub">Deye: <b data-live="manager-deye-mode">${currentMode || "—"}</b><b data-live="deye-mode" hidden>${currentMode || "—"}</b></div>
                  </div>
                </div>
                <div class="flow-status-tile">
                  <div class="flow-status-icon" style="color:#fbbf24">${this.iconSvg("clock")}</div>
                  <div class="flow-status-copy">
                    <span>Planowana decyzja</span>
                    <strong>${this.escapeHtml(plannedAction)}</strong>
                  </div>
                </div>
                <div class="flow-status-tile">
                  <div class="flow-status-icon" style="color:#4ade80">${this.iconSvg("gear")}</div>
                  <div class="flow-status-copy">
                    <span>Wykonana decyzja</span>
                    <strong>${this.escapeHtml(executedAction)}</strong>
                  </div>
                </div>
                <div class="flow-status-tile">
                  <div class="flow-status-icon" style="color:#38bdf8">${this.iconSvg("shield")}</div>
                  <div class="flow-status-copy">
                    <span>Tryb Managera</span>
                    <strong class="mode-${managerModeClass}" data-live="manager-mode">${modeText}</strong>
                    <div class="sub">Slot: <b data-live="active-slot">${activeSlotLabel}</b></div>
                  </div>
                </div>
              </div>
              <div class="flow-footer">Dane aktualizowane co 5 s</div>
            </div>
          </div>
        </div>
      </section>`;
  }

  scaleFlowPanel() {
    const wrapper = this.querySelector(".flow-wrapper");
    const scaler = this.querySelector(".flow-scaler");
    if (!wrapper || !scaler) return;
    if (this._flowResizeObserver && this._flowObservedWrapper !== wrapper) {
      this._flowResizeObserver.disconnect();
      this._flowObservedWrapper = wrapper;
      this._flowObservedWidth = wrapper.clientWidth || 0;
      this._flowResizeObserver.observe(wrapper);
    }
    const baseWidth = parseFloat(scaler.dataset.baseWidth) || 1328;
    const baseHeight = parseFloat(scaler.dataset.baseHeight) || 768;
    const available = wrapper.clientWidth || this.clientWidth || baseWidth;
    const scale = Math.min(1, Math.max(available / baseWidth, 0.2));
    scaler.style.transform = `scale(${scale})`;
    scaler.style.transformOrigin = "top left";
    wrapper.style.height = `${baseHeight * scale}px`;
    wrapper.style.overflow = "hidden";
  }
  updateFlowLines() {
    const st = (key) => this.asNumber(this.state(this.entity("sensor", key)), 0) || 0;
    const active = {
      pv: st("pv_power") > 1,
      gridImport: st("grid_power") > 1,
      gridExport: st("grid_power") < -1,
      batteryDischarge: st("battery_power") > 1,
      batteryCharge: st("battery_power") < -1,
      load: st("load_power") > 1,
    };
    const svg = this.querySelector(".flow-svg");
    if (!svg) return;
    const scaler = this.querySelector(".flow-scaler");
    const tileWidth = parseFloat(scaler?.dataset.tileWidth) || 300;
    const tileGap = parseFloat(scaler?.dataset.tileGap) || 0;
    const inverterColumnWidth = parseFloat(scaler?.dataset.inverterColumnWidth) || 640;
    const inverterVisualWidth = parseFloat(scaler?.dataset.inverterVisualWidth) || 190;
    const geometry = this.flowGeometry({ tileWidth, tileGap, inverterColumnWidth, inverterVisualWidth });
    const pvPath = geometry.paths.pvToInverter;
    const batPath = active.batteryCharge
      ? geometry.paths.inverterToBattery
      : geometry.paths.batteryToInverter;
    const gridPath = active.gridExport
      ? geometry.paths.inverterToGrid
      : geometry.paths.gridToInverter;
    const homePath = geometry.paths.inverterToHome;
    svg.setAttribute("viewBox", `0 0 ${geometry.boardWidth} ${geometry.boardHeight}`);
    const setPath = (key, d, color, isActive) => {
      const background = svg.querySelector(`path[data-flow-line-bg="${key}"]`);
      const path = svg.querySelector(`path[data-flow-line="${key}"]`);
      if (!path) return;
      background?.setAttribute("d", d);
      background?.setAttribute("stroke", color);
      path.setAttribute("d", d);
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-width", "4");
      path.setAttribute("stroke-opacity", isActive ? 0.96 : 0.18);
      if (isActive) path.setAttribute("marker-end", `url(#flow-arrow-${key})`);
      else path.removeAttribute("marker-end");
      path.textContent = "";
      path.classList.toggle("flow-active", isActive);
    };
    setPath("pv", pvPath, "#fbbf24", active.pv);
    setPath("battery", batPath, "#4ade80", active.batteryDischarge || active.batteryCharge);
    setPath("grid", gridPath, "#c084fc", active.gridImport || active.gridExport);
    setPath("home", homePath, "#38bdf8", active.load);
  }

  scheduleSlots() {
    return Array.from({ length: 24 }, (_, hour) => {
      const next = (hour + 1) % 24;
      const key = `${String(hour).padStart(2, "0")}_${String(next).padStart(2, "0")}`;
      const label = `${String(hour).padStart(2, "0")}:00-${String(next).padStart(2, "0")}:00`;
      const touSlot = hour < 4 ? 1 : hour < 8 ? 2 : hour < 12 ? 3 : hour < 16 ? 4 : hour < 20 ? 5 : 6;
      return [key, label, touSlot];
    });
  }

  async startSell() {
    const scheduler = this.entity("switch", "scheduler");
    const chargeScheduler = this.entity("switch", "charge_scheduler");
    const controlMode = this.entity("select", "control_mode");
    if (this.exists(controlMode)) await this.callService("select", "select_option", { entity_id: controlMode, option: "Schedule" });
    if (this.exists(scheduler)) await this.callService("switch", "turn_on", { entity_id: scheduler });
    if (this.exists(chargeScheduler)) await this.callService("switch", "turn_off", { entity_id: chargeScheduler });
  }

  async stopManager() {
    return this.applyDefaultValues();
  }

  async restoreDefaults() {
    return this.applyDefaultValues();
  }

  async resumeManager() {
    if (this._resumeApplying) return false;
    this._resumeApplying = true;
    this._defaultsStatus = "saving";
    this._defaultsMessage = "W\u0142\u0105czanie Managera i harmonogramu\u2026";
    this.beginSave();
    this.render();
    try {
      if (!this.hasService("deye_energy_manager", "resume_manager")) throw new Error("Us\u0142uga deye_energy_manager.resume_manager jest niedost\u0119pna");
      await this.callService("deye_energy_manager", "resume_manager", {});
      this._defaultsStatus = "saved";
      this._defaultsMessage = "W\u0142\u0105czono Manager i harmonogram";
      this._saveMessage = this._defaultsMessage;
      this.finishSave();
      return true;
    } catch (error) {
      this._defaultsStatus = "error";
      this._defaultsMessage = `Nie uda\u0142o si\u0119 w\u0142\u0105czy\u0107 Managera: ${error?.message || "brak potwierdzenia Home Assistant"}`;
      this.failSave("resume_manager", error);
      return false;
    } finally {
      this._resumeApplying = false;
      this.render();
    }
  }

  async applyDefaultValues() {
    if (this._defaultsApplying) return false;
    this._defaultsApplying = true;
    this._defaultsStatus = "saving";
    this._defaultsMessage = "Stosowanie ustawień domyślnych…";
    this.beginSave();
    this._saveMessage = this._defaultsMessage;
    this.updateSaveIndicator();
    this.updateDefaultApplyState();
    try {
      if (!this.hasService("deye_energy_manager", "restore_defaults")) {
        throw new Error("Usługa deye_energy_manager.restore_defaults jest niedostępna");
      }
      await this.callService("deye_energy_manager", "restore_defaults", {});
      this._defaultsStatus = "saved";
      this._defaultsMessage = "Zastosowano ustawienia domyślne";
      this._saveMessage = this._defaultsMessage;
      this.finishSave();
      return true;
    } catch (error) {
      this._defaultsStatus = "error";
      this._defaultsMessage = `Nie udało się potwierdzić pełnego zestawu ustawień domyślnych: ${error?.message || "brak potwierdzenia Home Assistant"}`;
      this.failSave("restore_defaults", error);
      this._saveMessage = this._defaultsMessage;
      this.updateSaveIndicator();
      return false;
    } finally {
      this._defaultsApplying = false;
      this.updateDefaultApplyState();
    }
  }

  normalizeManagerMode(value) {
    const raw = value === null || value === undefined ? "" : String(value).trim();
    return ({
      "Selling First": "Sprzedaż",
      Sell: "Sprzedaż",
      "Sprzedaż": "Sprzedaż",
      Charge: "Ładowanie",
      "Ładowanie": "Ładowanie",
      normal: "Normalna Praca",
      "Normalna Praca": "Normalna Praca",
      "Zero Export To Load": "Normalna Praca",
      "Zero Export To CT": "Normalna Praca",
      "Zero Export": "Normalna Praca",
      Essentials: "Normalna Praca",
    })[raw] || raw;
  }

  slotWorkModes() {
    return ["Normalna Praca", "Sprzedaż", "Ładowanie"];
  }

  slotModeLabel(mode) {
    return this.normalizeManagerMode(mode);
  }

  slotModeOptions() {
    return this.slotWorkModes().map((mode) => [mode, this.slotModeLabel(mode)]);
  }

  modeMeta(mode, enabled = true) {
    if (!enabled) {
      return { cls: "disabled", title: "Wy\u0142\u0105czono", subtitle: "Slot nieaktywny", icon: "shield" };
    }
    const normalized = this.normalizeManagerMode(mode);
    if (normalized === "Sprzedaż") {
      return { cls: "selling", title: "Sprzeda\u017c", subtitle: "Priorytet sprzeda\u017cy", icon: "sell" };
    }
    if (normalized === "Normalna Praca") {
      return { cls: "normal", title: "Normalna Praca", subtitle: "Normalny tryb pracy", icon: "normal" };
    }
    if (normalized === "Ładowanie") {
      return { cls: "charge", title: "\u0141adowanie", subtitle: "\u0141adowanie z sieci", icon: "charge" };
    }
    return { cls: "disabled", title: "Brak danych", subtitle: "Nieznany tryb pracy", icon: "shield" };
  }

  modeTextClass(text) {
    const normalized = this.norm(text);
    if (normalized.includes("sprzeda") || normalized.includes("selling")) return "selling";
    if (normalized.includes("normal") || normalized.includes("zeroexport") || normalized.includes("ct") || normalized.includes("load")) return "normal";
    if (normalized.includes("adowan") || normalized.includes("charge")) return "charge";
    if (normalized.includes("wylacz") || normalized.includes("disabled") || normalized.includes("idle") || normalized.includes("brak danych")) return "disabled";
    return "";
  }

  iconSvg(type) {
    const icons = {
      sell: '<svg viewBox="0 0 24 24"><path d="M4 14h4l2-6 4 12 2-6h4"/><path d="M4 18h16"/></svg>',
      load: '<svg viewBox="0 0 24 24"><path d="M6 12h6V6l6 6h-6v6z"/><path d="M4 20h16"/></svg>',
      ct: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="6"/><path d="M12 8v8M8 12h8"/></svg>',
      charge: '<svg viewBox="0 0 24 24"><path d="M13 2 5 13h6l-1 9 8-12h-6z"/></svg>',
      shield: '<svg viewBox="0 0 24 24"><path d="M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6z"/><path d="M9 12l2 2 4-5"/></svg>',
      normal: '<svg viewBox="0 0 24 24"><path d="M3 12h2v7h14v-7h2"/><path d="M5 10l7-7 7 7"/><path d="M9 21v-6h6v6"/><path d="M12 3v4"/></svg>',
      edit: '<svg viewBox="0 0 24 24"><path d="M4 20h4l11-11-4-4L4 16z"/><path d="M13 6l4 4"/></svg>',
      gear: '<svg viewBox="0 0 24 24"><path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/><path d="M4 12h2m12 0h2M12 4v2m0 12v2M6.3 6.3l1.4 1.4m8.6 8.6 1.4 1.4m0-11.4-1.4 1.4m-8.6 8.6-1.4 1.4"/></svg>',
      ai: '<svg viewBox="0 0 24 24"><path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z"/><path d="M18 15l.8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8z"/></svg>',
      info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 10v6"/><path d="M12 7h.01"/></svg>',
      check: '<svg viewBox="0 0 24 24"><path d="M5 12l4 4L19 6"/></svg>',
      copy: '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M5 16H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
      close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
      pv: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3"/><path d="M12 2v2M12 12v2M6 8H4m16 0h-2M7.8 3.8 6.4 2.4m9.8 1.4 1.4-1.4"/><path d="M4 17h16l-2 5H6z"/></svg>',
      pv2: '<svg viewBox="0 0 64 64"><circle cx="18" cy="17" r="8.5" fill="#fbbf24" stroke="#fde68a" stroke-width="2"/><path d="M18 3v5M18 26v5M4 17h5M27 17h5M8.2 7.2l3.6 3.6M24.2 23.2l3.6 3.6M8.2 26.8l3.6-3.6M24.2 10.8l3.6-3.6" stroke="#fbbf24" stroke-width="3" stroke-linecap="round" fill="none"/><path d="M17 30h38l-6 22H11z" fill="#60a5fa" stroke="#93c5fd" stroke-width="2" stroke-linejoin="round"/><path d="M24 30l-4 22M36 30l-1 22M48 30l3 22M14 41h38" stroke="#1e3a8a" stroke-width="2" fill="none"/><path d="M31 52v7M23 59h17" stroke="#6b8298" stroke-width="3" fill="none"/></svg>',
      home: '<svg viewBox="0 0 24 24"><path d="m3 11 9-8 9 8"/><path d="M5 10v11h14V10M9 21v-7h6v7"/></svg>',
      home2: '<svg viewBox="0 0 64 64"><path d="M7 31 32 9l25 22" fill="none" stroke="#18baff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 28v29h15V41h9v16h15V28" fill="none" stroke="#18baff" stroke-width="6" stroke-linejoin="round"/><path d="M46 13h8v13" fill="none" stroke="#497b9f" stroke-width="4"/></svg>',
      grid: '<svg viewBox="0 0 24 24"><path d="M12 2 6 22m6-20 6 20M8 8h8M6 14h12M4 22h16"/></svg>',
      grid2: '<svg viewBox="0 0 64 64"><path d="M32 5 11 19h42zM32 5 19 59M32 5l13 54M16 30h32M13 43h38M7 59h50" fill="none" stroke="#c064f7" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/><path d="m18 19 14 11 14-11M19 30l13 13 13-13M16 43l16 16 16-16" fill="none" stroke="#d08aff" stroke-width="2.5" stroke-linejoin="round"/></svg>',
      battery: '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="17" height="12" rx="2"/><path d="M20 10h2v4h-2M7 12h9M11 8v8"/></svg>',
      battery2: '<svg viewBox="0 0 64 64"><rect x="18" y="4" width="28" height="6" rx="2" fill="#24c84f" stroke="#69f58d" stroke-width="2"/><rect x="10" y="9" width="44" height="51" rx="6" fill="#20c94e" fill-opacity=".76" stroke="#58ef79" stroke-width="3"/><path d="M15 17h34v10H15zM15 31h34v10H15zM15 45h34v10H15z" fill="#3ee96a" fill-opacity=".42" stroke="none"/><path d="m34 16-12 23h11l-4 19 15-27H33z" fill="#effff3" stroke="#caffd6" stroke-width="1.5" stroke-linejoin="round"/></svg>',
      clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
      thermometer: '<svg viewBox="0 0 24 24"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/><circle cx="11.5" cy="18.5" r="1.5"/></svg>',
      chart: '<svg viewBox="0 0 24 24"><path d="M4 20V10m6 10V4m6 16v-7m4 7H2"/></svg>',
      zap: '<svg viewBox="0 0 24 24"><path d="M13 2 5 13h6l-1 9 8-12h-6z"/></svg>',
      money: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M15 8.5c-.8-.7-1.8-1-3-1-1.7 0-3 .9-3 2s1 1.8 3 2.2 3 1.1 3 2.3-1.3 2-3 2c-1.3 0-2.5-.4-3.3-1.2M12 5v14"/></svg>',
      calendar: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18M8 14h.01m4 0h.01m4 0h.01M8 18h.01m4 0h.01"/></svg>',
      weather: '<svg viewBox="0 0 24 24"><circle cx="8" cy="8" r="3"/><path d="M8 2v2M2 8h2M3.8 3.8l1.4 1.4M13 8h2M10.8 5.2l1.4-1.4"/><path d="M7 19h10a4 4 0 0 0 0-8 6 6 0 0 0-11.3 2A3 3 0 0 0 7 19z"/></svg>',
    };
    return icons[type] || icons.gear;
  }

  iconButton(icon, label, dataAttr = "") {
    return `<button class="icon-action" ${dataAttr} title="${label}">${this.iconSvg(icon)}<span>${label}</span></button>`;
  }

  modeLegend() {
    return this.slotWorkModes().concat(["Wy\u0142\u0105czone"]).map((mode) => {
      const meta = mode === "Wy\u0142\u0105czone" ? this.modeMeta("", false) : this.modeMeta(mode, true);
      return `<div class="mode-tile ${meta.cls}">
        <div class="mode-icon">${this.iconSvg(meta.icon)}</div>
        <div><strong>${meta.title}</strong><span>${meta.subtitle}</span></div>
      </div>`;
    }).join("");
  }

  modePill(mode, enabled) {
    const meta = this.modeMeta(mode, enabled);
    return `<span class="mode-pill ${meta.cls}">${meta.title}</span>`;
  }

  slotSummary(entities, enabled) {
    if (!enabled) return `<span class="empty-value">-</span>`;
    const mode = this.displayState(entities.mode, "Normalna Praca");
    const sell = this.numberState(entities.sellPower, 0);
    const discharge = this.numberState(entities.dischargeCurrent, 0);
    const charge = this.numberState(entities.chargeCurrent, 0);
    const soc = this.numberState(entities.touSoc, 0);
    return `
      <span class="metric sell">${this.iconSvg("sell")} ${sell} W</span>
      <span class="metric discharge">\u2193 ${discharge} A</span>
      <span class="metric charge">\u2191 ${charge} A</span>
      <span class="metric soc">\u25c7 ${soc}%</span>
      <span class="sr-only">${this.slotModeLabel(mode)}</span>`;
  }

  selectedSlotList(slots) {
    return slots.filter(([key]) => this._selectedSlots?.has(key));
  }

  selectedRangeText(slots) {
    const selected = this.selectedSlotList(slots);
    if (!selected.length) return "Brak zaznaczonych godzin";
    const labels = selected.map(([, label]) => label);
    if (selected.length === 1) return labels[0];
    const first = labels[0].slice(0, 5);
    const last = labels[labels.length - 1].slice(6, 11);
    return `${first} - ${last}`;
  }

  bulkValues(slots) {
    const selected = this.selectedSlotList(slots);
    const [key, label] = selected[0] || slots[0] || [];
    if (!key) {
      return {
        active: "off",
        mode: "Sprzedaż",
        sellPower: 0,
        dischargeCurrent: 0,
        chargeCurrent: 0,
        minimumSellSoc: 0,
        minSellPrice: 0,
      };
    }
    const entities = this.slotEntities(key, label);
    return {
      active: this.displayState(entities.sellEnabled, "off") === "on" ? "on" : "off",
      mode: this.normalizeManagerMode(this.displayState(entities.mode, "Sprzedaż")),
      sellPower: this.numberState(entities.sellPower, 0),
      dischargeCurrent: this.numberState(entities.dischargeCurrent, 0),
      chargeCurrent: this.numberState(entities.chargeCurrent, 0),
      minimumSellSoc: this.numberState(entities.minimumSellSoc, 0),
      minSellPrice: this.numberState(entities.minSellPrice, 0),
    };
  }

  syncBulkPanelValues(slots) {
    if (!this._selectionMode || !this.selectedSlotList(slots).length || this.isInteracting()) return;
    const bulk = this.bulkValues(slots);
    const values = {
      "multi-active": bulk.active,
      "multi-mode": bulk.mode,
      "multi-sell-power": bulk.sellPower,
      "multi-discharge-current": bulk.dischargeCurrent,
      "multi-charge-current": bulk.chargeCurrent,
      "multi-min-soc": bulk.minimumSellSoc,
      "multi-min-sell-price": bulk.minSellPrice,
    };
    Object.entries(values).forEach(([name, value]) => {
      this.querySelectorAll(`[data-raw="${name}"]`).forEach((el) => {
        if (this.ownerDocument?.activeElement !== el) el.value = value;
      });
    });
  }

  scheduleSegments(slots) {
    const backendPlan = this.mappingPlanDiagnostics();
    if (backendPlan.length) {
      return backendPlan.map((item) => ({
        start: Number(item.start),
        end: Number(item.end),
        touSoc: this.asNumber(item.tou_soc),
        chargeEnabled: Boolean(item.grid_charge),
      }));
    }
    const rows = slots.map(([key, label]) => {
      const entities = this.slotEntities(key, label);
      const enabled = this.displayState(entities.sellEnabled) === "on";
      const mode = enabled ? this.normalizeManagerMode(this.displayState(entities.mode, "Normalna Praca")) : "Wy\u0142\u0105czone";
      const isCharge = enabled && mode === "Ładowanie";
        const slotTouSoc = this.asNumber(this.numberState(entities.touSoc, ""));
        const data = {
          key,
          label,
          start: Number(key.slice(0, 2)),
          end: key.endsWith("_00") ? 0 : Number(key.slice(3, 5)),
          enabled,
          mode,
          sellPower: this.asNumber(this.numberState(entities.sellPower, 0)) || 0,
          dischargeCurrent: this.numberState(entities.dischargeCurrent, "brak"),
          chargeCurrent: this.numberState(entities.chargeCurrent, "brak"),
          gridChargeCurrent: this.numberState(entities.gridChargeCurrent, "brak"),
          minimumSellSoc: this.asNumber(this.numberState(entities.minimumSellSoc, 0)) || 0,
          minSellPrice: this.asNumber(this.numberState(entities.minSellPrice, 0)) || 0,
          // Physical Deye TOU SOC is always tou_soc, independent of the logical mode.
          touSoc: slotTouSoc,
          chargeMode: isCharge,
          chargeEnabled: isCharge && this.displayState(entities.chargeEnabled, "off") === "on",
        };
        return data;
      });
      // Awaryjny podgląd dla starszego backendu. Źródłem prawdy jest mapping_plan
      // z diagnostyki Managera, używany również do fizycznego zapisu Deye TOU.
      // The physical 24h -> 6/6 key is (touSoc, chargeEnabled) only; mode and the
      // logical sale guard minimumSellSoc never affect the physical mapping.
      const same = (a, b) => ["touSoc", "chargeEnabled"].every((key) => a[key] === b[key]);
    const segments = [];
    rows.forEach((row) => {
      if (segments.length && same(segments[segments.length - 1], row)) {
        segments[segments.length - 1].end = row.end;
      } else {
        segments.push({ ...row });
      }
    });
    while (segments.length < 6) {
      let splitIndex = -1;
      let longest = 0;
      segments.forEach((segment, index) => {
        const end = segment.end === 0 ? 24 : segment.end;
        const duration = end - segment.start;
        if (duration > longest && duration > 1) {
          longest = duration;
          splitIndex = index;
        }
      });
      if (splitIndex < 0) break;
      const segment = segments[splitIndex];
      const end = segment.end === 0 ? 24 : segment.end;
      const middle = segment.start + Math.floor((end - segment.start) / 2);
      segments.splice(
        splitIndex,
        1,
        { ...segment, end: middle },
        { ...segment, start: middle },
      );
    }
    return segments;
  }

  mapWarning(slots) {
    const count = this.scheduleSegments(slots).length;
    const capability = this.fullTouCapability();
    if (capability.ok !== true) {
      return `<span class="bad">Brak pełnego mapowania Deye Time Of Use</span>`;
    }
    if (count === 6) return `<span class="good">OK: 6/6 zakres\u00f3w Deye</span>`;
    if (count > 6) return `<span class="bad">Za du\u017co zmian: ${count}/6 zakres\u00f3w Deye</span>`;
    return `<span class="bad">Niepe\u0142ne mapowanie: ${count}/6 zakres\u00f3w Deye</span>`;
  }

  aiSuggestions(slots) {
    const settings = this.aiSettings();
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const learning = aiState?.attributes?.learning_summary || {};
    const sellPriceToday = this.entity("sensor", ["sell_price_today", "energy_price"]);
    const buyPriceToday = this.entity("sensor", "buy_price_today");
    const buyPriceTomorrow = this.entity("sensor", "buy_price_tomorrow");
    const solcastMetrics = aiState?.attributes?.solcast_current_day || {};
    const hasCanonicalSolcast = Object.keys(solcastMetrics).length > 0;
    const solcastToday = hasCanonicalSolcast
      ? (this.asNumber(solcastMetrics.forecast_today_kwh) ?? 0)
      : (this.asNumber(this.state(this.entity("sensor", "solcast_forecast_today"), 0)) ?? 0);
    const solcastRemaining = hasCanonicalSolcast
      ? (this.asNumber(solcastMetrics.remaining_forecast_kwh) ?? 0)
      : (this.asNumber(this.state(this.entity("sensor", "solcast_remaining_today"), 0)) ?? 0);
    const dailyPv = hasCanonicalSolcast
      ? (this.asNumber(solcastMetrics.production_today_kwh) ?? 0)
      : (this.asNumber(this.state(this.entity("sensor", "daily_pv_production"), 0)) ?? 0);
    const soldToday = this.asNumber(this.state(this.entity("sensor", "sold_energy_today"), 0)) || 0;
    const [sellPrices] = this.canonicalPriceMaps("sell");
    const [buyPrices, buyPricesTomorrow] = this.canonicalPriceMaps("buy");
    const tariff = this.tariffData();
    const todayKey = this.localDateKey();
    const tomorrowDate = new Date();
    tomorrowDate.setDate(tomorrowDate.getDate() + 1);
    const tomorrowKey = this.localDateKey(tomorrowDate);
    // Backend rows already contain the final effective BUY price.  Never add
    // OSD again in the browser (notably for Pstryk all-in gross prices).
    const totalBuyPrices = new Map(buyPrices);
    const totalBuyPricesTomorrow = new Map(buyPricesTomorrow);
    const minSell = this.asNumber(settings.minSellPrice) ?? 0;
    const maxBuy = this.asNumber(settings.maxBuyPrice) ?? Number.POSITIVE_INFINITY;
    const profileRows = Array.isArray(learning.hourly_profile) ? learning.hourly_profile : [];
    const profileByHour = new Map(profileRows.map((row) => [Number(String(row.hour || "0").slice(0, 2)), row]));
    const hourlySurplus = new Map(profileRows.map((row) => {
      const hour = Number(String(row.hour || "0").slice(0, 2));
      return [hour, (this.asNumber(row.pv_kwh) || 0) - (this.asNumber(row.load_kwh) || 0)];
    }));
    const maxSurplus = Math.max(0.001, ...[...hourlySurplus.values()].map((value) => Math.max(0, value)));
    const surplusWeight = settings.strategy === "autoconsumption" ? 0.25 : settings.strategy === "balanced" ? 0.12 : 0.04;
    const sellRanking = new Map([...sellPrices.entries()].map(([hour, price]) => [
      hour,
      (settings.prices ? price : 0) + (Math.max(0, hourlySurplus.get(hour) || 0) / maxSurplus) * (settings.prices ? surplusWeight : 1),
    ]));
    const bestSell = [...sellPrices.entries()]
      .filter(([, price]) => !settings.prices || price >= minSell)
      .sort((a, b) => (sellRanking.get(b[0]) || b[1]) - (sellRanking.get(a[0]) || a[1]))
      .slice(0, 4);
    const cheapBuy = [...totalBuyPrices.entries()].filter(([, price]) => price <= maxBuy).sort((a, b) => a[1] - b[1]).slice(0, 4);
    const cheapBuy48 = [
      ...[...totalBuyPrices.entries()].map(([hour, price]) => ({ day: "Dziś", date: todayKey, hour, price })),
      ...[...totalBuyPricesTomorrow.entries()].map(([hour, price]) => ({ day: "Jutro", date: tomorrowKey, hour, price })),
    ].filter((row) => row.price <= maxBuy).sort((a, b) => a.price - b.price).slice(0, 8);
    const activeConfigured = slots.filter(([key, label]) => {
      const e = this.slotEntities(key, label);
      return this.state(e.sellEnabled) === "on";
    }).length;
    const margin = Math.max(0, this.asNumber(settings.forecastMargin) ?? 0) / 100;
    const historicalCorrection = this.asNumber(learning.solcast_correction_factor);
    const forecastCorrection = settings.forecastEnabled && settings.history && settings.realPv
      ? (historicalCorrection ?? 1)
      : 1;
    const weatherRiskFactor = settings.forecastEnabled
      ? (this.asNumber(learning.weather?.risk_factor) ?? 1)
      : 1;
    const currentHour = new Date().getHours();
    const expectedRemainingPv = profileRows
      .filter((row) => Number(String(row.hour || "0").slice(0, 2)) >= currentHour)
      .reduce((sum, row) => sum + (this.asNumber(row.pv_kwh) || 0), 0);
    const forecastBase = settings.forecastEnabled ? solcastRemaining : expectedRemainingPv;
    const usableForecast = Math.max(0, forecastBase * forecastCorrection * weatherRiskFactor * (1 - margin));
    const expectedRemainingLoad = profileRows
      .filter((row) => Number(String(row.hour || "0").slice(0, 2)) >= currentHour)
      .reduce((sum, row) => sum + (this.asNumber(row.load_kwh) || 0), 0);
    const reserveKwh = Math.max(0, this.asNumber(settings.reserveKwh) || 0);
    const estimatedSurplus = Math.max(0, usableForecast - expectedRemainingLoad - reserveKwh);
    const solcastGap = solcastToday > 0 ? Math.max(0, estimatedSurplus - soldToday) : 0;
    const learningReady = (this.asNumber(learning.recorded_hours) || 0) >= 24;
    const soc = this.optionalSocNumber(this.state(this.entity("sensor", "battery_soc")));
    const batteryCapacityKwh = Math.max(0.1, this.asNumber(settings.batteryCapacityKwh) || 10);
    const batteryEfficiency = Math.max(0.5, Math.min(1, (this.asNumber(settings.batteryEfficiency) || 90) / 100));
    const storedEnergyKwh = soc === null
      ? null
      : batteryCapacityKwh * Math.max(0, Math.min(100, soc)) / 100;
    const protectedEnergyKwh = batteryCapacityKwh * Math.max(0, Math.min(100, this.asNumber(settings.minSoc) || 0)) / 100;
    const usableBatteryKwh = storedEnergyKwh === null
      ? 0
      : Math.max(0, storedEnergyKwh - protectedEnergyKwh - reserveKwh) * batteryEfficiency;
    const targetEnergyKwh = batteryCapacityKwh * Math.max(0, Math.min(100, this.asNumber(settings.targetSoc) || 0)) / 100;
    const chargeNeedKwh = storedEnergyKwh === null
      ? 0
      : Math.max(0, targetEnergyKwh - storedEnergyKwh - Math.max(0, usableForecast - expectedRemainingLoad));
    const sellableEnergyKwh = estimatedSurplus + (settings.allowBatterySell ? usableBatteryKwh : 0);
    const predictedSoc = this.asNumber(profileByHour.get((currentHour + 1) % 24)?.soc_avg);
    const predictedSocTrend = estimatedSurplus > 1 ? "wzrost" : usableForecast < expectedRemainingLoad ? "spadek" : "stabilny";
    return {
      bestSell,
      cheapBuy,
      cheapBuy48,
      totalBuyPrices,
      totalBuyPricesTomorrow,
      tariff,
      settings,
      activeConfigured,
      solcastToday,
      solcastRemaining,
      solcastMetrics,
      usableForecast,
      dailyPv,
      forecastCorrection,
      weatherRiskFactor,
      solcastGap,
      learning,
      learningReady,
      profileByHour,
      sellRanking,
      expectedRemainingLoad,
      expectedRemainingPv,
      estimatedSurplus,
      predictedSocTrend,
      predictedSoc,
      soc,
      batteryCapacityKwh,
      batteryEfficiency,
      storedEnergyKwh,
      usableBatteryKwh,
      chargeNeedKwh,
      sellableEnergyKwh,
    };
  }

  aiPlannerData(slots) {
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const backend = aiState?.attributes?.planner_48h;
    if (backend && Array.isArray(backend.rows) && backend.rows.length) return backend;
    return {
      rows: [],
      days: [],
      checkpoints: {},
      data_quality: { learning_stage: "brak planu", recorded_days: 0, tomorrow_sell_prices: 0, tomorrow_buy_prices: 0, weather_hours: 0 },
      variants: {},
      selected_strategy: "balanced",
      generated_at: "",
      plan_status: "blocked",
      recommended_write: false,
      diagnostic_only: true,
      diagnostic_message: "Brak planu — backendowy Optimizer Core jest niedostępny.",
    };
  }

  aiRowsForDay(planner, day = this._aiDay) {
    return (Array.isArray(planner?.rows) ? planner.rows : [])
      .filter((row) => row.day === day)
      .sort((a, b) => Number(a.hour) - Number(b.hour));
  }

  aiRepresentativeProposal(rows) {
    let representative = null;
    let representativeOrder = Number.POSITIVE_INFINITY;
    (Array.isArray(rows) ? rows : []).forEach((row, index) => {
      const dayOrder = row?.day === "today" ? 0 : row?.day === "tomorrow" ? 1 : 2;
      const hour = this.asNumber(row?.hour);
      const order = dayOrder * 100 + (hour === null ? 24 : Math.max(0, Math.min(23, hour))) + index / 1000;
      if (order < representativeOrder) {
        representative = row;
        representativeOrder = order;
      }
    });
    return representative;
  }

  aiSlotEconomics(row) {
    return {
      slotResult: this.asNumber(row?.net_result ?? row?.balance_pln),
      baselineSlotDelta: this.asNumber(row?.benefit),
      terminalValue: this.asNumber(row?.terminal_value),
      marginalDecisionBenefit: null,
    };
  }

  aiSlotKey(hour) {
    const start = String(Number(hour)).padStart(2, "0");
    const end = String((Number(hour) + 1) % 24).padStart(2, "0");
    return `${start}_${end}`;
  }

  aiSelection(day = this._aiDay) {
    if (!this._aiSelections || !(this._aiSelections[day] instanceof Set)) {
      this._aiSelections = this._aiSelections || {};
      this._aiSelections[day] = new Set();
    }
    return this._aiSelections[day];
  }

  aiProfileId(row) {
    if (row?.profile_id) return String(row.profile_id);
    const source = String(row?.decision_source || "");
    if (source.startsWith("profile:")) return source.slice(8);
    const reason = (row?.reason_codes || []).find((code) => String(code).startsWith("profile:"));
    return reason ? String(reason).slice(8) : "";
  }

  aiPlannedSlotPower(row) {
    if (row?.action !== "sell" && row?.action !== "charge") return 0;
    const contractPower = this.asNumber(row?.action_contract?.schedule_update?.sell_power);
    const maxPower = this.effectiveInverterMaxPowerW();
    if (contractPower !== null && contractPower > 0 && contractPower <= maxPower) return contractPower;
    const explicit = this.asNumber(row.planned_power_w);
    if (explicit !== null && explicit > 0 && explicit <= maxPower) return explicit;
    // Compatibility fallback for older ai_state payloads that did not expose
    // the canonical write value. New plans always use the contract above.
    const energy = this.asNumber(row.planned_energy_kwh ?? row.energy_kwh);
    const duration = this.asNumber(row.duration_minutes);
    const calculated = energy !== null && energy > 1e-6 && duration !== null && duration > 0
      ? Math.round(energy * 1000 * 60 / duration)
      : 0;
    if (Number.isFinite(calculated) && calculated > 0 && calculated <= maxPower) return calculated;
    return 0;
  }

  aiIsApplicableProposal(row) {
    if (!row?.proposed) return false;
    if (row?.action_contract?.deployment_ready === false) return false;
    const energy = this.asNumber(row.planned_energy_kwh ?? row.energy_kwh);
    if (energy === null || energy <= 1e-6) return false;
    if (row.action === "sell" && this.aiPlannedSlotPower(row) <= 0) return false;
    if (!this.aiProfileId(row) && (this.asNumber(row.benefit) || 0) <= 0.005) return false;
    return row.action === "sell" || row.action === "charge";
  }

  aiIsPreviewCandidate(row) {
    return (row?.candidate_action === "sell" || row?.candidate_action === "charge")
      && (!row?.proposed || Boolean(row?.proposal_block_reason) || Boolean(row?.deployment_block_reason));
  }

  aiCanSelectProposal(planner, row, day = this._aiDay) {
    const readiness = planner?.execution_readiness?.by_day?.[day]?.status;
    const recommendation = planner?.recommended_write_by_day?.[day];
    return this.aiIsApplicableProposal(row)
      && !this.aiIsPreviewCandidate(row)
      && readiness === "confirmable"
      && recommendation?.allowed === true;
  }

  initialiseAiSelections(planner) {
    this._aiSelections = { today: new Set(), tomorrow: new Set() };
    ["today", "tomorrow"].forEach((day) => {
      this.aiRowsForDay(planner, day)
        .filter((row) => this.aiCanSelectProposal(planner, row, day))
        .forEach((row) => this._aiSelections[day].add(this.aiSlotKey(row.hour)));
    });
  }

  aiRowUpdate(row) {
    if (!this.aiIsApplicableProposal(row)) return null;
    const contractUpdate = row?.action_contract?.schedule_update;
    if (contractUpdate && typeof contractUpdate === "object") {
      // Core Sell is power-only.  This action must never forward a legacy
      // derived battery current into the global maximum-discharge entity.
      const allowed = row.action === "sell"
        ? new Set(["slot_key", "enabled", "mode", "sell_power"])
        : new Set([
          "slot_key", "enabled", "mode", "sell_power", "discharge_current",
          "charge_current", "grid_charge_current", "minimum_sell_soc", "tou_soc",
          "min_sell_price", "charge_enabled",
        ]);
      const exact = {};
      Object.entries(contractUpdate).forEach(([field, value]) => {
        if (allowed.has(field) && value !== null && value !== undefined) exact[field] = value;
      });
      if (exact.slot_key !== this.aiSlotKey(row.hour)) return null;
      return exact;
    }
    const selling = row.action === "sell";
    const charging = row.action === "charge";
    const update = {
      slot_key: this.aiSlotKey(row.hour),
      enabled: true,
      mode: selling ? "Sprzedaż" : charging ? "Ładowanie" : "Normalna Praca",
    };
    // The selected proposal contract is authoritative for this special action.
    // Apply Today materialises all unselected hours as Normal Operation on the
    // backend, without duplicating that business rule in the card.
    // Unrelated current, SOC and price fields are intentionally preserved.
    if (selling) update.sell_power = this.aiPlannedSlotPower(row);
    if (charging) {
      const profile = this.chargeProfileStoredValues();
      const numericFields = {
        charge_current: profile.charge_current,
        discharge_current: profile.discharge_current,
        grid_charge_current: profile.grid_charge_current,
        tou_soc: profile.target_soc,
      };
      Object.entries(numericFields).forEach(([field, value]) => {
        const number = this.asNumber(value);
        if (number !== null) update[field] = number;
      });
      if (typeof profile.grid_charge_enabled === "boolean") {
        update.charge_enabled = profile.grid_charge_enabled;
      }
    }
    return update;
  }

  async applyAiDayPlan(slots, day = this._aiDay) {
    const planner = this.aiPlannerData(slots);
    const dayRecommendation = planner.recommended_write_by_day?.[day];
    const writeAllowed = dayRecommendation ? dayRecommendation.allowed !== false : planner.recommended_write !== false;
    if (!writeAllowed || planner.plan_status === "blocked") {
      window.alert(planner.plan_status === "blocked"
        ? "Plan jest zablokowany z powodu krytycznego braku danych."
        : dayRecommendation?.reason === "learning_dry_run"
          ? "Optimizer Core nadal się uczy. Plan jest widoczny w trybie dry-run, ale wdrożenie pozostaje zablokowane do osiągnięcia etapu apply_allowed."
        : dayRecommendation?.reason === "financial_data_incomplete"
          ? `Plan dla dnia „${day === "today" ? "dzisiaj" : "jutro"}” ma niekompletne dane finansowe i nie może zostać zapisany.`
          : `Plan dla wybranego dnia można analizować, ale nie jest rekomendowany do zapisu (${this.aiUiText(dayRecommendation?.reason || "no_recommended_changes")}).`);
      return;
    }
    const selected = this.aiSelection(day);
    const rows = this.aiRowsForDay(planner, day)
      .filter((row) => this.aiCanSelectProposal(planner, row, day) && selected.has(this.aiSlotKey(row.hour)));
    if (!rows.length) return;
    const label = day === "today" ? "zastosować dziś" : "zaplanować na jutro";
    const preview = rows.map((row) => {
      const power = this.aiPlannedSlotPower(row);
      const energy = this.aiFormatNumber(row.planned_energy_kwh ?? row.energy_kwh, 2);
      const update = this.aiRowUpdate(row) || {};
      const chargeContract = row.action === "charge"
        ? `, prąd ładowania ${this.aiFormatNumber(update.charge_current, 1)} A, rozładowania ${this.aiFormatNumber(update.discharge_current, 1)} A, z sieci ${this.aiFormatNumber(update.grid_charge_current, 1)} A, SOC ${this.aiFormatNumber(update.tou_soc, 0)}%, Grid Charge ${update.charge_enabled ? "włączone" : "wyłączone"}`
        : "";
      return `${row.label || this.hourLabel(row.hour)}: ${this.aiActionLabel(row.action)}, ${power} W, około ${energy} kWh${chargeContract}`;
    }).join("\n");
    const scopeNotice = day === "today"
      ? "Zaznaczone pozycje będą jedynymi specjalnymi akcjami dzisiejszego planu. Wszystkie pozostałe godziny — także odznaczone propozycje i stare akcje — zostaną ustawione jako Normalna Praca."
      : "Zaznaczone pozycje będą jedynymi specjalnymi akcjami jutrzejszego planu. Wszystkie pozostałe godziny — także odznaczone propozycje i stare akcje — mają cel Normalna Praca. Dzisiaj zostanie zapisana wyłącznie intencja; każdy bieżący slot zostanie wykonany jutro JIT.";
    if (!window.confirm(`Czy ${label} ${rows.length} wybranych zmian?\n\n${preview}\n\n${scopeNotice}`)) return;
    const updates = rows.map((row) => this.aiRowUpdate(row)).filter(Boolean);
    if (updates.length !== rows.length) {
      window.alert("Plan zmienił się lub zawiera niespójne dane. Odśwież Sugestie AI i wybierz godziny ponownie.");
      return;
    }
    if (day === "today") {
      const date = rows[0]?.date;
      if (!await this.applySchedulePatch(updates, { replaceDay: true, date })) return;
      await this.startSell();
      this.saveAiAnalysis(this.aiSuggestions(slots), "accepted", {
        segmentCount: rows.length,
        accepted: true,
        day,
        selectedHours: rows.map((row) => row.label),
      });
      this._dialog = null;
    } else {
      const date = rows[0]?.date;
      const impacts = new Map((planner.profile_impacts || []).map((item) => [String(item.profile_id || ""), item]));
      const slotValidations = Object.fromEntries(rows.map((row) => {
        const profileRoot = impacts.get(this.aiProfileId(row)) || {};
        const profile = profileRoot.days?.[date] || profileRoot;
        const deadline = row.deadline || profile.deadline || null;
        const startHour = Number(String(profile.start || "00:00").slice(0, 2));
        const deadlineHour = deadline ? Number(String(deadline).slice(0, 2)) : null;
        return [this.aiSlotKey(row.hour), {
          profile_id: this.aiProfileId(row) || null,
          action: row.action,
          purpose: row.purpose || profile.purpose || null,
          minimum_price: profile.minimum_price ?? 0,
          maximum_effective_price: profile.maximum_effective_price ?? 0,
          planned_price: row.action === "sell" ? row.sell_price : row.effective_buy_price,
          minimum_soc: row.action_contract?.effective_min_soc ?? row.effective_min_soc_pct ?? row.hard_min_soc_pct ?? 0,
          allow_partial: row.action_contract?.allow_partial ?? (profile.allow_partial !== false),
          target_energy_kwh: profile.requested_energy_kwh ?? 0,
          planned_energy_kwh: row.planned_energy_kwh ?? 0,
          duration_minutes: row.duration_minutes ?? 60,
          power_limit_w: row.action_contract?.planned_power_w ?? row.planned_power_w ?? row.power_limit_w ?? null,
          possible_energy_kwh: profile.possible_energy_kwh ?? row.planned_energy_kwh ?? 0,
          remaining_target_kwh: profile.remaining_energy_kwh ?? profile.requested_energy_kwh ?? 0,
          min_net_result: profile.min_net_result ?? 0,
          profile_net_result_pln: profile.profile_net_result_pln ?? 0,
          deadline,
          deadline_next_day: deadlineHour !== null && deadlineHour <= startHour,
          charge_source: profile.source || row.charge_source || null,
          preserve_pv_room: profile.preserve_pv_room === true,
          max_soc_before_pv_pct: row.max_soc_before_pv_pct ?? null,
        }];
      }));
      try {
        await this.callService("deye_energy_manager", "save_future_plan", {
          data: JSON.stringify({
            date,
            plan_id: planner.plan_id,
            strategy: planner.selected_strategy,
            replace_day: true,
            labels: rows.map((row) => row.label),
            updates,
            slot_validations: slotValidations,
          }),
        });
        this._saveStatus = "saved";
        this._saveMessage = `Plan zapisany na ${this.aiFormatDate(date)} · ${rows.length} slotów · ${rows.map((row) => row.label || this.hourLabel(row.hour)).join(", ")} · strategia ${this.aiUiText(planner.selected_strategy || "balanced")}`;
      } catch (err) {
        this._saveStatus = "error";
        this._saveMessage = `Błąd planu na jutro: ${err?.message || err}`;
      }
    }
    this.render();
  }

  aiConfidenceClass(value) {
    const confidence = this.asNumber(value) || 0;
    return confidence >= 75 ? "good" : confidence >= 50 ? "warn" : "bad";
  }

  aiFormatNumber(value, digits = 2) {
    const number = this.asNumber(value);
    return number === null
      ? "brak danych"
      : new Intl.NumberFormat("pl-PL", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(number);
  }

  aiReadableKeyFactor(value) {
    const raw = String(value ?? "");
    const separator = raw.indexOf("=");
    const rawKey = separator >= 0 ? raw.slice(0, separator).trim() : raw.trim();
    const rawValue = separator >= 0 ? raw.slice(separator + 1).trim() : "";
    const key = rawKey.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const numeric = this.asNumber(rawValue.replace("%", "").replace(",", "."));
    const known = {
      cena_sprzedazy: ["Cena tej godziny", " zł/kWh", 2],
      soc_start: ["SOC na starcie", "%", 1],
      rezerwa: ["Rezerwa", "%", 1],
      najlepsza_pozniejsza_cena: ["Najlepsza późniejsza cena", " zł/kWh", 2],
    };
    if (known[key]) {
      const [label, unit, digits] = known[key];
      const formatted = numeric === null ? "brak danych" : this.aiFormatNumber(numeric, digits);
      return `${label}: ${formatted}${numeric === null ? "" : unit}`;
    }
    const translated = this.aiUiText(rawKey);
    const label = translated
      ? translated.charAt(0).toUpperCase() + translated.slice(1)
      : "Współczynnik";
    const formatted = numeric === null ? (rawValue || "brak danych") : this.aiFormatNumber(numeric, 2);
    return `${label}: ${formatted}`;
  }

  aiFormatPercent(value, digits = 0) {
    const number = this.asNumber(value);
    return number === null ? "brak danych" : `${this.aiFormatNumber(number, digits)}%`;
  }

  aiQualityCoverage(value, total, unit = "") {
    const number = this.asNumber(value);
    if (number === null) return "brak danych";
    const suffix = unit ? ` ${unit}` : "";
    return `${this.aiFormatNumber(number, 0)}/${total}${suffix}`;
  }

  aiFormatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return this.escapeHtml(String(value || "brak"));
    return new Intl.DateTimeFormat("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
  }

  aiUiText(value) {
    const text = String(value ?? "");
    const labels = {
      proposal: "Propozycja",
      planned: "Ujęto w planie obliczeniowym",
      validated: "Zweryfikowano",
      pending: "Oczekuje na potwierdzenie",
      approved: "Oczekuje",
      logical_applied: "Zapisano logicznie",
      physical_pending: "Oczekuje na falownik",
      confirmed: "Potwierdzono",
      skipped: "Nie zastosowano",
      blocked: "Zablokowano",
      failed: "Błąd wykonania",
      manual: "Zmieniono ręcznie",
      disabled: "Profil wyłączony",
      ready: "Plan gotowy",
      completed: "Plan wykonany",
      waiting: "Oczekuje na rozpoczęcie",
      running: "W trakcie realizacji",
      partial: "Częściowa realizacja",
      blocked_partial_not_allowed: "Profil niewykonany — częściowa realizacja jest wyłączona",
      blocked_min_net_result: "Profil zablokowany — zbyt niski wynik netto",
      partial_not_allowed: "Częściowa realizacja jest wyłączona",
      min_net_result: "Wynik netto poniżej wymaganego minimum",
      cancelled: "Anulowano",
      manual_override: "Zmieniono ręcznie",
      missed: "Pominięto",
      superseded: "Zastąpiono",
      legacy_unconfirmed: "Stary wynik bez potwierdzenia fizycznego",
      partially_executed: "Plan częściowo wykonany",
      no_qualified_hours: "Brak godzin spełniających warunki",
      no_hours_above_minimum: "Brak godzin spełniających cenę minimalną",
      partially_possible: "Cel częściowo możliwy",
      proposal_pending: "Plan utworzony — oczekuje na zatwierdzenie",
      forecast_ready: "Prognoza utworzona",
      startup_or_restored_state: "Stan odtworzony po uruchomieniu",
      startup: "Uruchamianie planu",
      input_snapshot_changed: "Dane wejściowe zmienione",
      settings_changed: "Ustawienia zmienione",
      user_profiles_changed: "Profile użytkownika zmienione",
      cached_until_input_change: "Wynik z pamięci — dane wejściowe bez zmian",
      "comparison:practically-the-same": "Wynik praktycznie taki sam jak plan bazowy",
      "optimizer:high-net-export-price": "Wysoka cena sprzedaży",
      "optimizer:profitable-charge-before-sale": "Opłacalne ładowanie przed sprzedażą",
      "optimizer:no-profitable-change": "Brak opłacalnej zmiany",
      "optimizer:none": "Brak zmiany optymalizatora",
      "safety:missing-load-forecast": "Brak prognozy zużycia domu — działanie wstrzymane",
      "limit:minimum_soc": "Ograniczenie: minimalny SOC",
      "limit:target_soc": "Ograniczenie: docelowy SOC",
      "limit:action_power_limit": "Ograniczenie: moc ustawiona dla profilu",
      "limit:battery_discharge_limit": "Ograniczenie: maksymalna moc rozładowania baterii",
      "limit:profile_max_power": "Ograniczenie: maksymalna moc profilu",
      "limit:global_max_sell_power": "Ograniczenie: globalna maksymalna moc sprzedaży",
      "limit:export_limit": "Ograniczenie: limit eksportu do sieci",
      "limit:inverter_power": "Ograniczenie: moc falownika",
      "limit:max_sell_power_entity": "Ograniczenie: encja Max Sell Power",
      "limit:current_voltage_battery_limit": "Ograniczenie: moc baterii wynikająca z prądu i napięcia",
      "limit:configured_battery_discharge_limit": "Ograniczenie: skonfigurowany limit rozładowania baterii",
      "limit:started_hour_duration": "Ograniczenie: pozostały czas rozpoczętej godziny",
      "limit:grid_export_limit": "Ograniczenie: maksymalny eksport do sieci",
      "limit:inverter_ac_limit": "Ograniczenie: moc AC falownika",
      "limit:physical_energy_budget": "Ograniczenie: dostępny budżet energii",
      "limit:higher_value_slot_reserved": "Energia zachowana dla droższej godziny tego profilu",
      "limit:dynamic_power_cap": "Ograniczenie: dynamiczny limit mocy godziny",
      "limit:residual_below_minimum": "Pozostała energia wymagałaby zbyt małej mocy",
      "limit:minimum_auto_sell_power": "Ograniczenie: minimalna moc automatycznej sprzedaży",
      "limit:grid_import_limit": "Ograniczenie: limit poboru z sieci",
      "limit:missing_current_soc_fail_closed": "Brak SOC — plan bezpiecznie zablokowany",
      higher_priority_profile_reserve: "Energia zachowana dla profilu o wyższym priorytecie",
      pv_only_profile: "Profil dopuszcza ładowanie wyłącznie z PV",
      pv_curtailed_by_export_or_inverter_limit: "Produkcja PV ograniczona limitem eksportu lub falownika",
      price_filter_or_no_qualified_hours: "Brak godzin spełniających warunki cenowe",
      core_budget_exceeded: "Przekroczono budżet obliczeń Core",
      operation_budget_exceeded: "Przekroczono budżet obliczeń Core",
      price_mapping_cache_invalidated: "Przeliczono po zmianie mapowania cen",
      core_blocked_missing_soc: "Brak wiarygodnych danych SOC",
      missing_load_forecast: "Brak prognozy zużycia domu",
      slot_elapsed: "Godzina już się zakończyła",
      missing_current_soc_fail_closed: "Brak SOC — plan bezpiecznie zablokowany",
      minimum_soc: "minimalny SOC",
      target_soc: "docelowy SOC",
      action_power_limit: "moc profilu",
      battery_discharge_limit: "maksymalna moc rozładowania baterii",
      profile_max_power: "maksymalna moc profilu",
      global_max_sell_power: "globalna maksymalna moc sprzedaży",
      export_limit: "limit eksportu do sieci",
      inverter_power: "moc falownika",
      max_sell_power_entity: "encja Max Sell Power",
      current_voltage_battery_limit: "moc baterii wynikająca z prądu i napięcia",
      configured_battery_discharge_limit: "skonfigurowany limit rozładowania baterii",
      started_hour_duration: "pozostały czas rozpoczętej godziny",
      grid_export_limit: "maksymalny eksport do sieci",
      inverter_ac_limit: "moc AC falownika",
      physical_energy_budget: "dostępny budżet energii",
      higher_value_slot_reserved: "energia zachowana dla droższej godziny tego profilu",
      near_equal_price_group: "grupa godzin o zbliżonych cenach",
      peak_power_balancing: "wyrównanie mocy w grupie zbliżonych cen",
      dynamic_power_cap: "dynamiczny limit mocy godziny",
      residual_below_minimum: "pozostała energia poniżej minimalnej mocy automatycznej",
      minimum_auto_sell_power: "minimalna moc automatycznej sprzedaży",
      grid_import_limit: "limit poboru z sieci",
      no_economic_headroom: "brak ekonomicznego zapasu w lepszych godzinach",
      pv_headroom_value: "wartość miejsca na prognozowaną produkcję PV",
      profile_energy_budget: "budżet energii profilu",
      unresolved_daily_constraint: "nierozstrzygnięte ograniczenie dziennego celu profilu",
      profile_energy_allocation: "podział energii celu pomiędzy godziny",
      optimizer_energy_allocation: "podział energii optymalizatora",
      price_threshold: "minimalna cena sprzedaży",
      target_reached: "cel profilu osiągnięty",
      past_window: "godzina już minęła",
      inactive_day: "profil nie jest aktywny w tym dniu",
      missing_prices: "Brak kompletnych danych cenowych",
      below_minimum_price: "cena poniżej minimum",
      not_selected_by_energy_budget: "energia zachowana dla korzystniejszych godzin lub rezerwy",
      mixed: "automatycznie — cel mieszany",
      awaiting_publication: "oczekiwanie na publikację cen po 13:00",
      missing_after_publication: "brak cen po oczekiwanej godzinie publikacji",
      financial_data_incomplete: "niekompletne dane finansowe dnia",
      profile_confirmation_available: "profil użytkownika gotowy do ręcznego zatwierdzenia",
      positive_day_benefit: "dodatni wynik dnia względem planu bazowego",
      terminal_value_delta: "różnica wartości terminalnej baterii",
      no_recommended_changes: "brak zmian rekomendowanych do zapisu",
      proposals_available: "Core utworzył propozycje dla tego dnia",
      confidence_below_minimum: "Pewność danych jest niższa od wymaganego minimum",
      profile_window_ended: "Okno aktywnego profilu nie jest teraz dostępne",
      current_plan_already_optimal: "Bieżący harmonogram jest już praktycznie optymalny",
      no_profitable_hours: "Brak opłacalnych godzin",
      no_proposals: "Brak propozycji",
      confidence_below_profile_minimum: "pewność niższa od minimum profilu",
      learning_evidence_insufficient: "niewystarczająca dojrzałość profilu",
      action_contract_not_deployment_ready: "kontrakt wykonania nie jest gotowy",
      critical_input_missing: "brak krytycznych danych",
      bootstrap: "Rozruch profilu",
      learning: "Uczenie aktywne",
      stable: "Profil stabilny",
      mature: "Profil dojrzały",
      preview: "Podgląd",
      confirmable: "Gotowy do potwierdzenia",
      "profile:morning_sale": "Profil: Poranna sprzedaż",
      "profile:evening_sale": "Profil: Wieczorna sprzedaż",
      "profile:charging": "Profil: Ładowanie",
      ok: "Gotowe",
      warning: "Ostrzeżenie",
      rejected: "Odrzucono",
      safe: "Bezpieczny",
      caution: "Wymaga ostrożności",
      unsafe: "Niebezpieczny",
      balanced: "Zrównoważony",
      profit: "Maksymalny zysk",
      explain: "Tylko wyjaśnienie",
      review: "Ocena i alternatywa",
      experimental: "Analiza eksperymentalna",
      valid: "Format odpowiedzi poprawny",
      connected: "Połączono",
      testing: "Testowanie",
      analysing: "Analizowanie",
      error: "Błąd",
      unavailable: "Niedostępne",
      unknown: "Stan nieznany",
      invalid: "Nieprawidłowa wartość",
      out_of_range: "Wartość poza zakresem",
      stale: "Dane nieaktualne",
      not_configured: "Nie skonfigurowano",
      own_soc_report: "Bezpośredni raport źródła SOC",
      sibling_health: "Stan źródła SOC potwierdzony przez powiązaną encję",
      event_observed_at: "Zmiana SOC zaobserwowana przez Home Assistant",
      last_updated_fallback: "Czas ostatniej aktualizacji encji SOC",
      compatibility_fallback: "Zastępcza ocena aktualności SOC",
      no_fresh_source_health: "Brak świeżego potwierdzenia źródła SOC",
      "Kandydaci są dostępni do podglądu; profil nie ma jeszcze wystarczającego evidence.": "Kandydaci są dostępni do podglądu; profil nie ma jeszcze wystarczających danych historycznych.",
    };
    if (labels[text]) return labels[text];
    if (text.startsWith("sibling_health:")) {
      return "Stan źródła SOC potwierdzony przez powiązaną encję";
    }
    if (text.startsWith("material_live_input_changed:")) {
      const field = text.slice("material_live_input_changed:".length);
      const fields = {
        battery_power: "Przeliczono po istotnej zmianie mocy baterii",
        grid: "Przeliczono po istotnej zmianie przepływu sieci",
        grid_power: "Przeliczono po istotnej zmianie mocy sieci",
        load: "Przeliczono po istotnej zmianie zużycia domu",
        load_power: "Przeliczono po istotnej zmianie mocy odbiorników",
        price_today: "Przeliczono po istotnej zmianie cen na dziś",
        price_tomorrow: "Przeliczono po istotnej zmianie cen na jutro",
        pv: "Przeliczono po istotnej zmianie produkcji PV",
        pv_power: "Przeliczono po istotnej zmianie mocy PV",
        soc: "Przeliczono po istotnej zmianie SOC",
        soc_freshness: "Przeliczono po zmianie aktualności danych SOC",
        soc_health: "Przeliczono po zmianie wiarygodności danych SOC",
        solcast: "Przeliczono po istotnej zmianie prognozy Solcast",
        weather: "Przeliczono po istotnej zmianie prognozy pogody",
      };
      return fields[field] || "Przeliczono po istotnej zmianie danych wejściowych";
    }
    if (text.includes(" / ")) {
      return text.split(" / ").map((item) => this.aiUiText(item)).join(" / ");
    }
    if (text.startsWith("limit:")) {
      return labels[text.slice("limit:".length)] || "Wystąpiło ograniczenie planu";
    }
    if (text.startsWith("optimizer:")) return "Zmiana wynika z obliczeń optymalizatora";
    if (text.startsWith("profile:")) return "Profil użytkownika";
    if (text.startsWith("safety:")) return "Działanie zablokowane ze względów bezpieczeństwa";
    if (text.startsWith("comparison:")) return "Porównano z planem bazowym";
    if (/^[a-z0-9]+(?:[_:.-][a-z0-9]+)+$/i.test(text)) {
      return "Wystąpiło ograniczenie planu";
    }
    return text;
  }

  aiActionLabel(action) {
    return {
      sell: "Sprzedaż",
      charge: "Ładowanie z sieci",
      charge_grid: "Ładowanie z sieci",
      charge_pv: "Ładowanie z PV",
      discharge_load: "Zasilanie domu z baterii",
      idle: "Bez zmiany",
      none: "Bez zmiany",
      "Selling First": "Priorytet sprzedaży",
    }[String(action || "")] || this.aiUiText(action || "none");
  }

  aiSourceLabel(row) {
    const source = String(row?.decision_source || "");
    if (source.startsWith("profile:")) return this.aiUiText(source);
    const profileId = this.aiProfileId(row);
    if (profileId) return this.aiUiText(`profile:${profileId}`);
    if (source === "optimizer") return "Optymalizator lokalny";
    if (source === "baseline") return "Plan bazowy";
    if ((row?.reason_codes || []).some((code) => String(code).startsWith("optimizer:"))) {
      return "Optymalizator lokalny";
    }
    return "Informacja cenowa";
  }

  aiSaleInsights(planner) {
    const backend = planner?.ui_insights?.sale_profiles;
    const profiles = this.aiProfiles().profiles || {};
    const maps = this.canonicalPriceMaps("sell", "final_price_pln_kwh", planner);
    const result = {};
    ["morning_sale", "evening_sale"].forEach((profileId) => {
      const configured = profiles[profileId] || {};
      const supplied = backend && typeof backend[profileId] === "object" ? backend[profileId] : {};
      const profile = { ...supplied, ...configured };
      const start = Number(String(profile.start || "00:00").slice(0, 2));
      const end = Number(String(profile.end || "00:00").slice(0, 2));
      const inWindow = (hour) => start < end ? hour >= start && hour < end : hour >= start || hour < end;
      const minimum = this.asNumber(
        configured.min_price
        ?? configured.minimum_price
        ?? supplied.minimum_price
        ?? supplied.min_price
      ) || 0;
      const days = {};
      ["today", "tomorrow"].forEach((day, dayIndex) => {
        const suppliedRows = Array.isArray(supplied.days?.[day]) ? supplied.days[day] : null;
        days[day] = (suppliedRows || [...maps[dayIndex].entries()]
          .filter(([hour]) => inWindow(hour))
          .map(([hour, price]) => ({
            day,
            hour,
            label: `${String(hour).padStart(2, "0")}:00–${String((hour + 1) % 24).padStart(2, "0")}:00`,
            sell_price: price,
            recommended: false,
            planned_energy_kwh: 0,
            planned_power_w: 0,
            soc_before: null,
            soc_after: null,
            decision_source: "informational",
          })))
          .map((row) => {
            const price = this.asNumber(row.sell_price);
            return {
              ...row,
              qualifies_minimum: typeof row.qualifies_minimum === "boolean"
                ? row.qualifies_minimum
                : price !== null && price + 1e-9 >= minimum,
            };
          });
      });
      const allRows = [...days.today, ...days.tomorrow];
      const qualified = allRows.filter((row) => row.qualifies_minimum).length;
      const target = this.asNumber(profile.target_energy_kwh) || 0;
      const calculatedPlanned = allRows
        .filter((row) => row.recommended)
        .reduce((sum, row) => sum + (this.asNumber(row.planned_energy_kwh) || 0), 0);
      const planned = this.asNumber(supplied.planned_energy_kwh);
      const effectivePlanned = planned === null ? calculatedPlanned : planned;
      const enabled = configured.enabled === undefined
        ? Boolean(supplied.enabled)
        : Boolean(configured.enabled);
      result[profileId] = {
        ...profile,
        profile_id: profileId,
        name: profile.name,
        enabled,
        start: profile.start,
        end: profile.end,
        target_energy_kwh: target,
        planned_energy_kwh: effectivePlanned,
        missing_energy_kwh: Math.max(0, target - effectivePlanned),
        minimum_price: minimum,
        minimum_soc_after: configured.min_soc_after
          ?? configured.minimum_soc_after
          ?? supplied.minimum_soc_after
          ?? supplied.min_soc_after,
        qualified_hours: qualified,
        status: !enabled
          ? "disabled"
          : qualified === 0
            ? "no_hours_above_minimum"
            : effectivePlanned + 1e-6 < target
              ? "partially_possible"
              : "ready",
        days,
      };
    });
    return result;
  }

  renderAiSaleRankings(planner) {
    const profiles = this.aiSaleInsights(planner);
    const renderDay = (profile, dayKey, dayLabel) => {
      const rows = Array.isArray(profile.days?.[dayKey]) ? profile.days[dayKey] : [];
      const ranked = rows.slice().sort((a, b) => (this.asNumber(b.sell_price) || 0) - (this.asNumber(a.sell_price) || 0) || a.hour - b.hour);
      const priceRanks = new Map(ranked.map((row, index) => [Number(row.hour), index + 1]));
      const visible = rows.slice().sort((a, b) => Number(a.hour) - Number(b.hour));
      return `<section class="ai-rank-day"><h5>${dayLabel}</h5>${visible.length ? visible.map((row) => {
        const recommended = profile.enabled && row.qualifies_minimum && row.recommended;
        const priceStatus = row.qualifies_minimum ? "Cena spełnia minimum" : "Poniżej ceny minimalnej";
        const priceRank = this.asNumber(row.price_rank) || priceRanks.get(Number(row.hour));
        const status = row.is_past ? "Godzina zakończona" : recommended ? "Zalecana" : priceStatus;
        return `<details class="ai-rank-row ${recommended ? "recommended" : "informational"}"><summary><span>${this.escapeHtml(row.label || this.hourLabel(row.hour))}</span><strong>${this.aiFormatNumber(row.sell_price, 2)} zł/kWh</strong><em>${status} · cena nr ${priceRank}</em></summary><div><span>Szacowana energia <b>${this.aiFormatNumber(row.planned_energy_kwh, 2)} kWh</b></span><span>Moc przekazywana do slotu <b>${this.aiPlannedSlotPower(row)} W</b></span><span>SOC <b>${this.aiFormatNumber(row.soc_before, 1)}% → ${this.aiFormatNumber(row.soc_after, 1)}%</b></span><span>${this.escapeHtml(row.skip_reason ? this.aiUiText(row.skip_reason) : priceStatus)}</span><span>Źródło: <b>${this.escapeHtml(this.aiSourceLabel(row))}</b></span></div></details>`;
      }).join("") : '<p class="ai-empty">Brak danych cenowych w tym oknie.</p>'}</section>`;
    };
    const section = (profileId, label) => {
      const profile = profiles[profileId] || {};
      const target = this.asNumber(profile.target_energy_kwh) || 0;
      const planned = this.asNumber(profile.planned_energy_kwh) || 0;
      const missing = this.asNumber(profile.missing_energy_kwh) || Math.max(0, target - planned);
      const noQualified = profile.enabled && Number(profile.qualified_hours) === 0;
      const primary = profile.explanation?.primary_constraint;
      return `<article class="ai-sale-profile ${profile.enabled ? "enabled" : "disabled"}"><header><div><h4>${label}</h4><strong>${profile.enabled ? "Profil włączony" : "Profil wyłączony"}</strong></div><div class="ai-profile-parameters"><span>Okno <b>${this.escapeHtml(profile.start || "--:--")}–${this.escapeHtml(profile.end || "--:--")}</b></span><span>Cel <b>${this.aiFormatNumber(target, 2)} kWh</b></span><span>Minimalna cena <b>${this.aiFormatNumber(profile.minimum_price, 2)} zł/kWh</b></span><span>Minimalny SOC po sprzedaży <b>${this.aiFormatNumber(profile.minimum_soc_after, 1)}%</b></span></div></header>${noQualified ? `<p class="ai-warning">Brak godzin spełniających minimalną cenę ${this.aiFormatNumber(profile.minimum_price, 2)} zł/kWh.</p>` : ""}${profile.enabled && missing > .001 ? `<p class="ai-warning">Cel: ${this.aiFormatNumber(target, 2)} kWh · możliwe do zaplanowania: ${this.aiFormatNumber(planned, 2)} kWh · brakuje: ${this.aiFormatNumber(missing, 2)} kWh. Główna przyczyna: ${this.escapeHtml(this.aiUiText(primary || "profile_energy_budget"))}.</p>` : ""}${!profile.enabled ? '<p class="ai-note">Poniżej pokazano wyłącznie godziny informacyjne. Wyłączony profil nie jest oznaczany jako realizowany.</p>' : ""}<div class="ai-price-columns">${renderDay(profile, "today", "Dziś")}${renderDay(profile, "tomorrow", "Jutro")}</div></article>`;
    };
    return `<div class="ai-sale-rankings">${section("morning_sale", "Poranna sprzedaż")}${section("evening_sale", "Wieczorna sprzedaż")}<details class="ai-other-hours"><summary>Pozostałe opłacalne godziny</summary><p>Pełny ranking informacyjny jest dostępny po włączeniu widoku 24 godzin w zakładce „Proponowane zmiany”.</p></details></div>`;
  }

  aiPurchaseInsights(planner) {
    const backend = planner?.ui_insights?.purchase_ranking;
    if (backend?.days) return backend;
    const tariff = this.tariffData();
    const rows = this.canonicalPriceRows("buy", planner);
    const days = {};
    ["today", "tomorrow"].forEach((day) => {
      days[day] = rows.filter((row) => row.day === day && this.asNumber(row.final_price_pln_kwh) !== null).map((row) => ({
        ...row, energy_price: row.energy_component, source_price: row.source_price_pln_kwh,
        distribution_price: row.added_distribution, effective_price: row.final_price_pln_kwh,
        price_includes_distribution: row.source_semantic_scope === "all_in_variable",
      })).sort((a, b) => (this.asNumber(a.effective_price) || 0) - (this.asNumber(b.effective_price) || 0) || a.hour - b.hour);
    });
    return {
      days, provider_name: tariff.provider_name, plan_name: tariff.plan_name,
      price_includes_distribution: tariff.price_includes_distribution,
      osd_complete: tariff.configured !== false,
      coverage_today: days.today.length, coverage_tomorrow: days.tomorrow.length,
      energy_source: this.entity("sensor", "buy_price_today"),
    };
  }

  renderAiPurchaseRanking(planner) {
    const ranking = this.aiPurchaseInsights(planner);
    const renderDay = (day, label) => {
      const available = Array.isArray(ranking.days?.[day]) ? ranking.days[day] : [];
      const ranked = available.slice().sort((a, b) => (this.asNumber(a.effective_price) || 0) - (this.asNumber(b.effective_price) || 0) || a.hour - b.hour);
      const priceRanks = new Map(ranked.map((row, index) => [Number(row.hour), index + 1]));
      const rows = ranked.slice(0, 8).sort((a, b) => Number(a.hour) - Number(b.hour));
      return `<section class="ai-rank-day"><h5>${label} · kolejność godzinowa</h5>${rows.length ? rows.map((row) => {
        const allIn = row.source_semantic_scope === "all_in_variable";
        const sourceLabel = allIn ? "Źródło pełne" : "Cena źródłowa";
        const extras = [
          !allIn && this.asNumber(row.distribution_price) ? `<span>Dystrybucja OSD <b>${this.aiFormatNumber(row.distribution_price, 2)} zł/kWh</b></span>` : "",
          this.asNumber(row.added_vat) ? `<span>Dodany VAT <b>${this.aiFormatNumber(row.added_vat, 2)} zł/kWh</b></span>` : "",
          this.asNumber(row.added_other_variable) ? `<span>Inne składniki zmienne <b>${this.aiFormatNumber(row.added_other_variable, 2)} zł/kWh</b></span>` : "",
        ].join("");
        return `<details class="ai-rank-row"><summary><span>${this.escapeHtml(row.label || this.hourLabel(row.hour))}</span><strong>Razem: ${this.aiFormatNumber(row.effective_price, 2)} zł/kWh</strong><em>Cena nr ${this.asNumber(row.price_rank) || priceRanks.get(Number(row.hour))} · ${this.escapeHtml(this.tariffZoneLabel(row.zone))}</em></summary><div><span>${sourceLabel} <b>${this.aiFormatNumber(row.source_price ?? row.energy_price, 2)} zł/kWh</b></span>${extras}<span>Razem <b>${this.aiFormatNumber(row.effective_price, 2)} zł/kWh</b></span><span>Adapter <b>${this.escapeHtml(row.source_adapter || "legacy")}</b> · ${this.escapeHtml(row.source_basis || "brak")} · ${this.escapeHtml(row.source_unit || "brak")}</span><span>${this.escapeHtml(row.provider_name || ranking.provider_name || "Brak operatora")} · ${this.escapeHtml(row.plan_name || ranking.plan_name || "brak taryfy")} · ${this.escapeHtml(this.aiUiText(row.day_type || "brak rodzaju dnia"))}</span></div></details>`;
      }).join("") : '<p class="ai-empty">Brak danych cenowych.</p>'}</section>`;
    };
    return `<div class="ai-purchase-ranking">${ranking.osd_complete ? "" : '<p class="ai-warning">Brak pełnych danych OSD — ranking zakupu jest orientacyjny. Ładowanie z sieci nie jest przedstawiane jako pewna opłacalna decyzja.</p>'}<div class="ai-tariff-summary"><span>Operator / taryfa <b>${this.escapeHtml(ranking.provider_name || "brak")} · ${this.escapeHtml(ranking.plan_name || "brak")}</b></span><span>Źródło ceny energii <b>${this.escapeHtml(ranking.energy_source || "brak")}</b></span><span>Dystrybucja <b>${ranking.price_includes_distribution ? "zawarta w cenie" : "doliczana z OSD"}</b></span><span>Pokrycie <b>dziś ${ranking.coverage_today || 0}/24 · jutro ${ranking.coverage_tomorrow || 0}/24</b></span></div><div class="ai-price-columns">${renderDay("today", "Dziś")}${renderDay("tomorrow", "Jutro")}</div></div>`;
  }

  aiLegacyWeatherCard(planner, day) {
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const weather = aiState?.attributes?.weather || {};
    const targetDate = new Date();
    if (day === "tomorrow") targetDate.setDate(targetDate.getDate() + 1);
    const targetKey = this.localDateKey(targetDate);
    const rawForecast = Array.isArray(weather.forecast) ? weather.forecast : [];
    const datedForecast = rawForecast.filter((row) => {
      const raw = row?.datetime ?? row?.time;
      if (!raw) return false;
      const stamp = new Date(raw);
      return !Number.isNaN(stamp.getTime()) && this.localDateKey(stamp) === targetKey;
    });
    const forecast = datedForecast.length ? datedForecast : rawForecast.slice(day === "today" ? 0 : 24, day === "today" ? 24 : 48);
    if (!weather.available || !forecast.length) {
      return `<section class="ai-metric-card ai-weather"><h3>Pogoda</h3><p class="ai-empty">Brak danych pogodowych</p><small>Solcast pozostaje źródłem podstawowym; nie zastosowano fikcyjnej korekty.</small></section>`;
    }
    const temperatures = forecast.map((row) => this.asNumber(row.temperature)).filter((value) => value !== null);
    const clouds = forecast.map((row) => this.asNumber(row.cloud_coverage)).filter((value) => value !== null);
    const rain = forecast.map((row) => this.asNumber(row.precipitation_probability)).filter((value) => value !== null);
    const average = (rows) => rows.length ? rows.reduce((sum, value) => sum + value, 0) / rows.length : null;
    const cloud = average(clouds);
    const risk = cloud === null ? null : Math.max(0.65, Math.min(1.05, 1 - cloud * 0.002 - (average(rain) || 0) * 0.001));
    return `<section class="ai-metric-card ai-weather"><h3>Pogoda</h3><div class="ai-weather-main"><span>${this.iconSvg("weather")}</span><strong>${temperatures.length ? `${average(temperatures).toFixed(1)}°C` : "brak temperatury"}</strong></div><p>${this.escapeHtml(String(forecast[0]?.condition || weather.condition || "brak"))}<br>Zachmurzenie: ${cloud === null ? "brak" : `${cloud.toFixed(0)}%`}<br>Opady: ${rain.length ? `${average(rain).toFixed(0)}%` : "brak"}</p><small>${risk === null ? "Bez korekty pogodowej" : `Pomocnicza korekta PV ×${risk.toFixed(2)}`}</small></section>`;
  }

  aiLegacyCompactEnergyChart(rows, title = "Plan energii") {
    const values = rows.length ? rows : [];
    const count = Math.max(1, values.length);
    const width = 760;
    const height = 236;
    const left = 38;
    const top = 24;
    const chartWidth = width - left - 16;
    const chartHeight = 158;
    const maxEnergy = Math.max(1, ...values.flatMap((row) => [this.asNumber(row.load_kwh) || 0, this.asNumber(row.pv_kwh) || 0]));
    const distributionValues = values.map((row) => this.asNumber(row.distribution) || 0).filter((value) => value > 0);
    const minDistribution = distributionValues.length ? Math.min(...distributionValues) : null;
    const step = chartWidth / count;
    const bars = values.map((row, index) => {
      const x = left + index * step;
      const loadHeight = (this.asNumber(row.load_kwh) || 0) / maxEnergy * chartHeight;
      const pvHeight = (this.asNumber(row.pv_kwh) || 0) / maxEnergy * chartHeight;
      const marker = row.action === "sell" ? "#7ee22d" : row.action === "charge" ? "#ffd166" : "transparent";
      const cheapZone = minDistribution !== null && (this.asNumber(row.distribution) || 0) <= minDistribution + .00001;
      const weatherMarker = this.asNumber(row.weather_factor) !== null && this.asNumber(row.weather_factor) < .9 ? "☁" : "";
      return `<rect x="${x.toFixed(1)}" y="${top}" width="${Math.max(1, step).toFixed(1)}" height="${chartHeight}" fill="${cheapZone ? "rgba(255,209,102,.055)" : "transparent"}"/><rect x="${x.toFixed(1)}" y="${(top + chartHeight - loadHeight).toFixed(1)}" width="${Math.max(2, step * .38).toFixed(1)}" height="${loadHeight.toFixed(1)}" fill="#32a8e8"/><rect x="${(x + step * .4).toFixed(1)}" y="${(top + chartHeight - pvHeight).toFixed(1)}" width="${Math.max(2, step * .38).toFixed(1)}" height="${pvHeight.toFixed(1)}" fill="#67bd2e"/><circle cx="${(x + step * .5).toFixed(1)}" cy="${top + 5}" r="3.5" fill="${marker}"/>${weatherMarker ? `<text x="${(x + step * .5).toFixed(1)}" y="${top + 19}" text-anchor="middle" fill="#a9c7d8" font-size="9">${weatherMarker}</text>` : ""}`;
    }).join("");
    const points = values.map((row, index) => `${(left + index * step + step / 2).toFixed(1)},${(top + chartHeight - (this.asNumber(row.soc_after) || 0) / 100 * chartHeight).toFixed(1)}`).join(" ");
    const labels = values.map((row, index) => index % (values.length > 24 ? 4 : 2) === 0
      ? `<text x="${(left + index * step).toFixed(1)}" y="${top + chartHeight + 18}" fill="#8fb0c2" font-size="9">${String(row.hour).padStart(2, "0")}</text>` : "").join("");
    return `<section class="ai-chart-card"><h3>${title}</h3><div class="ai-chart-legend"><span class="load">Zużycie</span><span class="pv">Produkcja PV</span><span class="soc">SOC</span><span class="sell">Sprzedaż</span><span class="charge">Ładowanie</span><span class="tariff">Tania dystrybucja</span></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${title}"><line x1="${left}" y1="${top + chartHeight}" x2="${width - 10}" y2="${top + chartHeight}" stroke="#24465a"/>${bars}<polyline points="${points}" fill="none" stroke="#ffd200" stroke-width="2.4"/>${labels}</svg></section>`;
  }

  aiWeatherMeta(condition) {
    const key = String(condition || "").toLowerCase();
    const values = {
      "clear-night": ["🌙", "bezchmurna noc"], cloudy: ["☁️", "pochmurno"], exceptional: ["⚠️", "warunki wyjątkowe"],
      fog: ["🌫️", "mgła"], hail: ["🌨️", "grad"], lightning: ["⛈️", "burza"], "lightning-rainy": ["⛈️", "burza z deszczem"],
      partlycloudy: ["🌤️", "częściowe zachmurzenie"], pouring: ["🌧️", "ulewa"], rainy: ["🌧️", "deszczowo"],
      snowy: ["🌨️", "śnieg"], "snowy-rainy": ["🌨️", "deszcz ze śniegiem"], sunny: ["☀️", "słonecznie"],
      windy: ["💨", "wietrznie"], "windy-variant": ["🌬️", "wietrznie z chmurami"],
    };
    return values[key] || ["🌡️", key || "brak danych"];
  }

  aiWeatherRows(weather, day, kind = "hourly") {
    const source = kind === "daily" ? weather.daily_forecast : weather.forecast;
    const rows = Array.isArray(source) ? source : [];
    if (kind === "daily") return rows;
    const target = new Date();
    if (day === "tomorrow") target.setDate(target.getDate() + 1);
    const targetKey = this.localDateKey(target);
    return rows.filter((row) => {
      const stamp = new Date(row?.datetime ?? row?.time ?? "");
      return !Number.isNaN(stamp.getTime()) && this.localDateKey(stamp) === targetKey;
    });
  }

  aiWeatherCard(planner, day) {
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const weather = aiState?.attributes?.weather || {};
    const hourly = this.aiWeatherRows(weather, day, "hourly");
    const daily = this.aiWeatherRows(weather, day, "daily");
    const target = new Date();
    if (day === "tomorrow") target.setDate(target.getDate() + 1);
    const targetKey = this.localDateKey(target);
    const dailyTarget = daily.find((row) => {
      const stamp = new Date(row?.datetime ?? row?.time ?? "");
      return !Number.isNaN(stamp.getTime()) && this.localDateKey(stamp) === targetKey;
    }) || {};
    const first = hourly[0] || dailyTarget;
    const currentCondition = day === "today" ? weather.condition : first?.condition;
    const [icon, label] = this.aiWeatherMeta(currentCondition);
    const number = (value, digits = 0, unit = "") => {
      const parsed = this.asNumber(value);
      return parsed === null ? "brak danych" : `${this.aiFormatNumber(parsed, digits)}${unit}`;
    };
    const temps = hourly.map((row) => this.asNumber(row.temperature)).filter((value) => value !== null);
    const high = this.asNumber(dailyTarget.temperature) ?? (temps.length ? Math.max(...temps) : null);
    const low = this.asNumber(dailyTarget.templow) ?? (temps.length ? Math.min(...temps) : null);
    const currentTemp = day === "today" ? this.asNumber(weather.temperature) : (this.asNumber(first?.temperature) ?? high);
    const dayNames = ["niedz.", "pon.", "wt.", "śr.", "czw.", "pt.", "sob."];
    const dailyStrip = daily.length ? daily.slice(0, 7).map((row) => {
      const stamp = new Date(row.datetime ?? row.time ?? "");
      const [rowIcon, rowLabel] = this.aiWeatherMeta(row.condition);
      return `<div class="ai-weather-day" title="${this.escapeHtml(rowLabel)}"><strong>${Number.isNaN(stamp.getTime()) ? "dzień" : dayNames[stamp.getDay()]}</strong><span>${rowIcon}</span><b>${number(row.temperature, 1, "°")}</b><small>${number(row.templow, 1, "°")}</small></div>`;
    }).join("") : `<p class="ai-empty">Brak prognozy dziennej</p>`;
    const hourlyStrip = hourly.length ? hourly.slice(0, 24).map((row) => {
      const stamp = new Date(row.datetime ?? row.time ?? "");
      const [rowIcon, rowLabel] = this.aiWeatherMeta(row.condition);
      return `<div class="ai-weather-hour" title="${this.escapeHtml(rowLabel)}"><strong>${Number.isNaN(stamp.getTime()) ? "--" : `${String(stamp.getHours()).padStart(2, "0")}:00`}</strong><span>${rowIcon}</span><b>${number(row.temperature, 0, "°")}</b><small>${number(row.precipitation_probability, 0, "%")}</small></div>`;
    }).join("") : `<p class="ai-empty">Brak prognozy godzinowej</p>`;
    if (!weather.available) {
      return `<section class="ai-metric-card ai-weather ai-weather-v2"><h3>Pogoda — ${day === "today" ? "dziś" : "jutro"}</h3><p class="ai-empty">Brak danych z ${this.escapeHtml(String(weather.entity_id || "encja nie została wskazana"))}</p><small>Solcast pozostaje źródłem podstawowym; brak danych pogodowych nie jest zastępowany zerami.</small></section>`;
    }
    return `<section class="ai-metric-card ai-weather ai-weather-v2"><div class="ai-weather-head"><div><span class="ai-weather-icon">${icon}</span><div><h3>${this.escapeHtml(label)}</h3><small>${day === "today" ? "Dziś" : "Jutro"} · aktualizacja ${this.formatTimeShort(weather.last_updated)}</small></div></div><div class="ai-weather-temperature"><strong>${currentTemp === null ? "--" : `${this.aiFormatNumber(currentTemp, 1)}°C`}</strong><span>${high === null ? "--" : this.aiFormatNumber(high, 1)}° / ${low === null ? "--" : this.aiFormatNumber(low, 1)}°</span></div></div><div class="ai-weather-facts"><span>Ciśnienie <b>${number(weather.pressure, 0, ` ${weather.pressure_unit || "hPa"}`)}</b></span><span>Wilgotność <b>${number(weather.humidity, 0, "%")}</b></span><span>Wiatr <b>${number(weather.wind_speed, 1, ` ${weather.wind_speed_unit || "km/h"}`)}${weather.wind_bearing ? ` · ${this.escapeHtml(String(weather.wind_bearing))}` : ""}</b></span></div><div class="ai-weather-tabs"><button class="${this._aiWeatherMode !== "hourly" ? "active" : ""}" data-ai-weather-mode="daily">Dzienna</button><button class="${this._aiWeatherMode === "hourly" ? "active" : ""}" data-ai-weather-mode="hourly">Godzinowa</button></div><div class="ai-weather-strip">${this._aiWeatherMode === "hourly" ? hourlyStrip : dailyStrip}</div><small class="ai-weather-source">Źródło: ${this.escapeHtml(String(weather.entity_id || "brak"))}${weather.last_error ? ` · ${this.escapeHtml(String(weather.last_error))}` : ""}. Solcast pozostaje prognozą podstawową.</small></section>`;
  }

  aiHistoricalHours() {
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const samples = Array.isArray(aiState?.attributes?.energy_samples) ? aiState.attributes.energy_samples.slice() : [];
    samples.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const result = new Map();
    samples.forEach((sample, index) => {
      const stamp = new Date(sample?.timestamp || "");
      if (Number.isNaN(stamp.getTime())) return;
      const next = new Date(samples[index + 1]?.timestamp || "");
      const minutes = Number.isNaN(next.getTime()) ? 5 : Math.max(0, Math.min(15, (next - stamp) / 60000));
      if (!minutes) return;
      const key = `${this.localDateKey(stamp)}-${stamp.getHours()}`;
      const row = result.get(key) || { pv: 0, load: 0, pvSamples: 0, loadSamples: 0 };
      const pv = this.asNumber(sample.pv_power);
      const load = this.asNumber(sample.load_power);
      if (pv !== null) { row.pv += Math.max(0, pv) * minutes / 60000; row.pvSamples += 1; }
      if (load !== null) { row.load += Math.max(0, load) * minutes / 60000; row.loadSamples += 1; }
      result.set(key, row);
    });
    return result;
  }

  aiLegacyDetailedEnergyChart(rows, title = "Plan energii") {
    const values = Array.isArray(rows) ? rows : [];
    const count = Math.max(1, values.length);
    const width = 1120, height = 455, left = 62, right = 54;
    const top = 48, topHeight = 185, weatherY = 256, socTop = 294, socHeight = 92, axisY = 414;
    const chartWidth = width - left - right;
    const step = chartWidth / count;
    const history = this.aiHistoricalHours();
    const weatherState = this._hass?.states?.[this.entity("sensor", "ai_state")]?.attributes?.weather || {};
    const weatherRows = Array.isArray(weatherState.forecast) ? weatherState.forecast : [];
    const weatherMap = new Map(weatherRows.map((row) => {
      const stamp = new Date(row?.datetime ?? row?.time ?? "");
      return Number.isNaN(stamp.getTime()) ? ["", null] : [`${this.localDateKey(stamp)}-${stamp.getHours()}`, row];
    }));
    const actual = values.map((row) => history.get(`${row.date}-${row.hour}`) || null);
    const energyValues = [];
    values.forEach((row, index) => {
      [actual[index]?.pvSamples ? actual[index].pv : null, actual[index]?.loadSamples ? actual[index].load : null,
        this.asNumber(row.solcast_kwh), this.asNumber(row.corrected_pv_kwh), this.asNumber(row.forecast_high_kwh), this.asNumber(row.load_kwh)]
        .forEach((value) => { if (value !== null) energyValues.push(Math.max(0, value)); });
    });
    const maxEnergy = Math.max(1, ...energyValues) * 1.08;
    const yEnergy = (value) => top + topHeight - Math.max(0, value) / maxEnergy * topHeight;
    const xCenter = (index) => left + index * step + step / 2;
    const distributionValues = values.map((row) => this.asNumber(row.distribution)).filter((value) => value !== null && value > 0);
    const minDistribution = distributionValues.length ? Math.min(...distributionValues) : null;
    const grid = [0, .25, .5, .75, 1].map((part) => `<line x1="${left}" y1="${(top + topHeight * part).toFixed(1)}" x2="${width - right}" y2="${(top + topHeight * part).toFixed(1)}" class="ai-chart-grid"/><text x="${left - 9}" y="${(top + topHeight * part + 4).toFixed(1)}" text-anchor="end" class="ai-chart-axis">${(maxEnergy * (1 - part)).toFixed(1)}</text>`).join("");
    const cheapZones = values.map((row, index) => {
      const rate = this.asNumber(row.distribution);
      const cheap = minDistribution !== null && rate !== null && rate <= minDistribution + .00001;
      return cheap ? `<rect x="${(left + index * step).toFixed(1)}" y="${top}" width="${Math.max(1, step).toFixed(1)}" height="${socTop + socHeight - top}" class="ai-cheap-zone"/>` : "";
    }).join("");
    const bars = values.map((row, index) => {
      const actualPv = actual[index]?.pvSamples ? actual[index].pv : null;
      const actualLoad = actual[index]?.loadSamples ? actual[index].load : null;
      const plannedLoad = this.asNumber(row.load_kwh);
      const solcast = this.asNumber(row.solcast_kwh);
      const bar = (value, offset, css) => value === null ? "" : `<rect x="${(left + index * step + step * offset).toFixed(1)}" y="${yEnergy(value).toFixed(1)}" width="${Math.max(2, step * .22).toFixed(1)}" height="${Math.max(0, top + topHeight - yEnergy(value)).toFixed(1)}" class="${css}"/>`;
      return `${bar(actualLoad ?? plannedLoad, .08, "ai-bar-load")}${bar(actualPv, .32, "ai-bar-actual")}${bar(solcast, .58, "ai-bar-solcast")}`;
    }).join("");
    const linePoints = (field, yFn = yEnergy) => values.map((row, index) => {
      const value = this.asNumber(row[field]);
      return value === null ? null : `${xCenter(index).toFixed(1)},${yFn(value).toFixed(1)}`;
    }).filter(Boolean).join(" ");
    const upper = values.map((row, index) => {
      const value = this.asNumber(row.forecast_high_kwh);
      return value === null ? null : `${xCenter(index).toFixed(1)},${yEnergy(value).toFixed(1)}`;
    }).filter(Boolean);
    const lower = values.map((row, index) => {
      const value = this.asNumber(row.forecast_low_kwh);
      return value === null ? null : `${xCenter(index).toFixed(1)},${yEnergy(value).toFixed(1)}`;
    }).filter(Boolean).reverse();
    const band = upper.length && lower.length ? `<polygon points="${[...upper, ...lower].join(" ")}" class="ai-forecast-band"/>` : "";
    const minSoc = this.asNumber(this.aiSettings()?.minSoc);
    const socY = (value) => socTop + socHeight - Math.max(0, Math.min(100, value)) / 100 * socHeight;
    const socLine = linePoints("soc_after", socY);
    const minSocLine = minSoc === null ? "" : `<line x1="${left}" y1="${socY(minSoc).toFixed(1)}" x2="${width - right}" y2="${socY(minSoc).toFixed(1)}" class="ai-min-soc"/><text x="${left + 4}" y="${(socY(minSoc) - 5).toFixed(1)}" class="ai-chart-axis">Min. SOC ${minSoc.toFixed(0)}%</text>`;
    const actions = values.map((row, index) => row.action === "sell" || row.action === "charge"
      ? `<rect x="${(left + index * step + step * .2).toFixed(1)}" y="${(socTop + socHeight - 15).toFixed(1)}" width="${Math.max(3, step * .6).toFixed(1)}" height="12" class="${row.action === "sell" ? "ai-action-sell" : "ai-action-charge"}"/>` : "").join("");
    const weatherIcons = values.map((row, index) => {
      const weather = weatherMap.get(`${row.date}-${row.hour}`);
      if (!weather) return "";
      const [icon] = this.aiWeatherMeta(weather.condition);
      return `<text x="${xCenter(index).toFixed(1)}" y="${weatherY}" text-anchor="middle" class="ai-chart-weather">${icon}</text>`;
    }).join("");
    const labels = values.map((row, index) => {
      const interval = values.length > 24 ? 4 : 2;
      return index % interval === 0 ? `<text x="${xCenter(index).toFixed(1)}" y="${axisY}" text-anchor="middle" class="ai-chart-axis">${String(row.hour).padStart(2, "0")}</text>` : "";
    }).join("");
    const daySeparator = values.length > 24 ? `<line x1="${(left + step * 24).toFixed(1)}" y1="${top - 20}" x2="${(left + step * 24).toFixed(1)}" y2="${socTop + socHeight}" class="ai-day-separator"/><text x="${left + step * 12}" y="${top - 25}" text-anchor="middle" class="ai-day-label">Dziś</text><text x="${left + step * 36}" y="${top - 25}" text-anchor="middle" class="ai-day-label">Jutro</text>` : "";
    const now = new Date();
    const nowIndex = values.findIndex((row) => row.date === this.localDateKey(now) && Number(row.hour) === now.getHours());
    const currentLine = nowIndex < 0 ? "" : `<line x1="${(left + step * (nowIndex + now.getMinutes() / 60)).toFixed(1)}" y1="${top - 5}" x2="${(left + step * (nowIndex + now.getMinutes() / 60)).toFixed(1)}" y2="${socTop + socHeight}" class="ai-now-line"/><text x="${(left + step * (nowIndex + now.getMinutes() / 60) + 4).toFixed(1)}" y="${top + 12}" class="ai-now-label">teraz</text>`;
    const chartId = `chart-${String(title).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    const display = (value, digits = 2, unit = "") => {
      const parsed = this.asNumber(value);
      return parsed === null ? "brak danych" : `${parsed.toFixed(digits)}${unit}`;
    };
    const tipSources = values.map((row, index) => {
      const actualRow = actual[index];
      const weather = weatherMap.get(`${row.date}-${row.hour}`) || {};
      const [, weatherLabel] = this.aiWeatherMeta(weather.condition);
      return `<div class="ai-chart-tip-source" data-ai-tip-source="${chartId}-${index}"><strong>${this.escapeHtml(String(row.date || ""))} · ${this.escapeHtml(String(row.label || this.hourLabel(row.hour)))}</strong><div><span>Produkcja rzeczywista</span><b>${actualRow?.pvSamples ? display(actualRow.pv, 2, " kWh") : "brak danych"}</b><span>Prognoza Solcast</span><b>${display(row.solcast_kwh, 2, " kWh")}</b><span>Prognoza skorygowana</span><b>${display(row.corrected_pv_kwh, 2, " kWh")}</b><span>Przedział prognozy</span><b>${display(row.forecast_low_kwh, 2)}–${display(row.forecast_high_kwh, 2, " kWh")}</b><span>Zużycie</span><b>${actualRow?.loadSamples ? display(actualRow.load, 2, " kWh") : display(row.load_kwh, 2, " kWh")}</b><span>SOC po</span><b>${display(row.soc_after, 1, "%")}</b><span>Działanie</span><b>${row.action === "sell" ? "sprzedaż" : row.action === "charge" ? "ładowanie" : "bez zmiany"}</b><span>Bilans</span><b>${display(row.balance_pln, 2, " PLN")}</b><span>Pogoda</span><b>${this.escapeHtml(weatherLabel)} · ${display(weather.temperature, 1, "°C")}</b><span>Pewność</span><b>${display(row.confidence, 0, "%")}</b></div></div>`;
    }).join("");
    const overlays = values.map((row, index) => `<rect x="${(left + index * step).toFixed(1)}" y="${top - 10}" width="${Math.max(1, step).toFixed(1)}" height="${socTop + socHeight - top + 10}" class="ai-chart-hit" data-ai-chart-point="${chartId}" data-ai-chart-index="${index}"/>`).join("");
    return `<section class="ai-chart-card ai-chart-v2" data-ai-chart="${chartId}"><h3>${this.escapeHtml(title)}</h3><div class="ai-chart-legend"><span class="load">Zużycie</span><span class="actual">Produkcja rzeczywista</span><span class="solcast">Prognoza Solcast</span><span class="corrected">Prognoza skorygowana</span><span class="band">Przedział prognozy</span><span class="soc">SOC</span><span class="sell">Sprzedaż</span><span class="charge">Ładowanie</span><span class="tariff">Tania dystrybucja</span></div><div class="ai-chart-scroll"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${this.escapeHtml(title)}"><text x="15" y="${top + 6}" class="ai-chart-axis">kWh</text>${cheapZones}${grid}${band}${bars}<polyline points="${linePoints("corrected_pv_kwh")}" class="ai-line-corrected"/><line x1="${left}" y1="${top + topHeight}" x2="${width - right}" y2="${top + topHeight}" class="ai-chart-baseline"/><text x="15" y="${socTop + 10}" class="ai-chart-axis">SOC</text><line x1="${left}" y1="${socTop}" x2="${width - right}" y2="${socTop}" class="ai-chart-grid"/><line x1="${left}" y1="${socTop + socHeight}" x2="${width - right}" y2="${socTop + socHeight}" class="ai-chart-baseline"/>${minSocLine}<polyline points="${socLine}" class="ai-line-soc"/>${actions}${weatherIcons}${labels}${daySeparator}${currentLine}<line class="ai-chart-crosshair-x" x1="0" x2="0" y1="${top}" y2="${socTop + socHeight}"/><line class="ai-chart-crosshair-y" x1="${left}" x2="${width - right}" y1="0" y2="0"/>${overlays}</svg></div><div class="ai-chart-tooltip" data-ai-chart-tooltip></div>${tipSources}<small class="ai-chart-help">Najedź kursorem lub dotknij godziny, aby zobaczyć szczegóły. Brakujące dane są oznaczane jako „brak danych”.</small></section>`;
  }

  aiLegacyReadableEnergyChart(rows, title = "Plan energii") {
    const values = Array.isArray(rows) ? rows : [];
    const is48h = values.length > 24;
    const count = Math.max(1, values.length);
    const width = is48h ? 1800 : 1080;
    const height = 610;
    const left = 76, right = 72, top = 58, plotHeight = 305;
    const axisY = 390, weatherTimeY = 423, weatherIconY = 451;
    const statusTop = 486, statusRowHeight = 31;
    const chartWidth = width - left - right;
    const step = chartWidth / count;
    const hidden = this._aiChartHiddenSeries instanceof Set ? this._aiChartHiddenSeries : new Set();
    const visible = (name) => !hidden.has(name);
    const history = this.aiHistoricalHours();
    const now = new Date();
    const todayKey = this.localDateKey(now);
    const actual = values.map((row) => {
      if (row.date !== todayKey || Number(row.hour) > now.getHours()) return null;
      return history.get(`${row.date}-${row.hour}`) || null;
    });
    const actualSource = (row, actualRow) => {
      if (row.date !== todayKey || Number(row.hour) > now.getHours()) return "Brak danych — godzina przyszła";
      if (Number(row.hour) === now.getHours()) return actualRow?.pvSamples ? "Bieżące — godzina częściowa" : "Brak danych";
      return actualRow?.pvSamples ? "Rzeczywiste" : "Brak danych";
    };
    const weatherState = this._hass?.states?.[this.entity("sensor", "ai_state")]?.attributes?.weather || {};
    const weatherRows = Array.isArray(weatherState.forecast) ? weatherState.forecast : [];
    const weatherMap = new Map(weatherRows.map((row) => {
      const stamp = new Date(row?.datetime ?? row?.time ?? "");
      return Number.isNaN(stamp.getTime()) ? ["", null] : [`${this.localDateKey(stamp)}-${stamp.getHours()}`, row];
    }));
    const energyNumbers = [];
    values.forEach((row, index) => {
      [actual[index]?.pvSamples ? actual[index].pv : null, actual[index]?.loadSamples ? actual[index].load : null,
        this.asNumber(row.load_kwh), this.asNumber(row.solcast_kwh), this.asNumber(row.corrected_pv_kwh), this.asNumber(row.forecast_high_kwh)]
        .forEach((value) => { if (value !== null) energyNumbers.push(Math.max(0, value)); });
    });
    const maxEnergy = Math.max(1, ...energyNumbers) * 1.08;
    const x = (index) => left + index * step + step / 2;
    const yEnergy = (value) => top + plotHeight - Math.max(0, value) / maxEnergy * plotHeight;
    const ySoc = (value) => top + plotHeight - Math.max(0, Math.min(100, value)) / 100 * plotHeight;
    const linePoints = (field, yFn) => values.map((row, index) => {
      const value = this.asNumber(row[field]);
      return value === null ? null : `${x(index).toFixed(1)},${yFn(value).toFixed(1)}`;
    }).filter(Boolean).join(" ");
    const horizontalGrid = [0, .2, .4, .6, .8, 1].map((part) => {
      const y = top + plotHeight * part;
      const energyLabel = maxEnergy * (1 - part);
      const socLabel = 100 * (1 - part);
      return `<line x1="${left}" y1="${y.toFixed(1)}" x2="${width - right}" y2="${y.toFixed(1)}" class="ai-readable-grid"/><text x="${left - 12}" y="${(y + 4).toFixed(1)}" text-anchor="end" class="ai-readable-axis">${energyLabel.toFixed(1)}</text><text x="${width - right + 12}" y="${(y + 4).toFixed(1)}" class="ai-readable-axis">${socLabel.toFixed(0)}</text>`;
    }).join("");
    const gridInterval = is48h ? 4 : 2;
    const verticalGrid = values.map((row, index) => index % gridInterval === 0
      ? `<line x1="${x(index).toFixed(1)}" y1="${top}" x2="${x(index).toFixed(1)}" y2="${top + plotHeight}" class="ai-readable-grid ai-readable-grid-v"/>` : "").join("");
    const bars = values.map((row, index) => {
      const actualRow = actual[index];
      const load = actualRow?.loadSamples ? actualRow.load : this.asNumber(row.load_kwh);
      const production = actualRow?.pvSamples ? actualRow.pv : null;
      const draw = (value, offset, css) => value === null ? "" : `<rect x="${(x(index) + step * offset - Math.max(2.5, step * .14)).toFixed(1)}" y="${yEnergy(value).toFixed(1)}" width="${Math.max(5, step * .28).toFixed(1)}" height="${Math.max(0, top + plotHeight - yEnergy(value)).toFixed(1)}" rx="1.5" class="${css}"/>`;
      return `${visible("load") ? draw(load, -.18, "ai-readable-load") : ""}${visible("actual") ? draw(production, .18, "ai-readable-actual") : ""}`;
    }).join("");
    const upper = values.map((row, index) => {
      const value = this.asNumber(row.forecast_high_kwh);
      return value === null ? null : `${x(index).toFixed(1)},${yEnergy(value).toFixed(1)}`;
    }).filter(Boolean);
    const lower = values.map((row, index) => {
      const value = this.asNumber(row.forecast_low_kwh);
      return value === null ? null : `${x(index).toFixed(1)},${yEnergy(value).toFixed(1)}`;
    }).filter(Boolean).reverse();
    const band = visible("band") && upper.length && lower.length ? `<polygon points="${[...upper, ...lower].join(" ")}" class="ai-readable-band"/>` : "";
    const solcastLine = visible("solcast") ? `<polyline points="${linePoints("solcast_kwh", yEnergy)}" class="ai-readable-solcast"/>` : "";
    const correctedLine = visible("corrected") ? `<polyline points="${linePoints("corrected_pv_kwh", yEnergy)}" class="ai-readable-corrected"/>` : "";
    const socLine = visible("soc") ? `<polyline points="${linePoints("soc_after", ySoc)}" class="ai-readable-soc"/>` : "";
    const minSoc = this.asNumber(this.aiSettings()?.minSoc);
    const minSocLine = visible("minimum") && minSoc !== null
      ? `<line x1="${left}" y1="${ySoc(minSoc).toFixed(1)}" x2="${width - right}" y2="${ySoc(minSoc).toFixed(1)}" class="ai-readable-min-soc"/><text x="${left + 7}" y="${(ySoc(minSoc) - 7).toFixed(1)}" class="ai-readable-min-label">Min. SOC ${minSoc.toFixed(0)}%</text>` : "";
    const xLabels = values.map((row, index) => index % gridInterval === 0
      ? `<text x="${x(index).toFixed(1)}" y="${axisY}" text-anchor="middle" class="ai-readable-hour">${String(row.hour).padStart(2, "0")}:00</text>` : "").join("");
    const weather = values.map((row, index) => {
      const forecast = weatherMap.get(`${row.date}-${row.hour}`);
      const meta = forecast ? this.aiWeatherMeta(forecast.condition) : ["—", "brak prognozy"];
      const precipitation = this.asNumber(forecast?.precipitation_probability);
      const rainClass = precipitation === null ? "missing" : precipitation >= 70 ? "high" : precipitation >= 35 ? "medium" : "low";
      return `<text x="${x(index).toFixed(1)}" y="${weatherIconY}" text-anchor="middle" class="ai-readable-weather">${meta[0]}</text><rect x="${(x(index) - Math.max(3, step * .25)).toFixed(1)}" y="${weatherIconY + 9}" width="${Math.max(6, step * .5).toFixed(1)}" height="3" rx="1.5" class="ai-weather-risk ${rainClass}"/>`;
    }).join("");
    const distributionValues = values.map((row) => this.asNumber(row.distribution)).filter((value) => value !== null && value > 0);
    const minDistribution = distributionValues.length ? Math.min(...distributionValues) : null;
    const statuses = values.map((row, index) => {
      const cellX = left + index * step + step * .08;
      const cellWidth = Math.max(3, step * .84);
      const selling = row.action === "sell";
      const charging = row.action === "charge";
      const rate = this.asNumber(row.distribution);
      const cheap = minDistribution !== null && rate !== null && rate <= minDistribution + .00001;
      return `${selling ? `<rect x="${cellX.toFixed(1)}" y="${(statusTop + 5).toFixed(1)}" width="${cellWidth.toFixed(1)}" height="${statusRowHeight - 10}" rx="3" class="ai-status-sell"/>` : ""}${charging ? `<rect x="${cellX.toFixed(1)}" y="${(statusTop + statusRowHeight + 5).toFixed(1)}" width="${cellWidth.toFixed(1)}" height="${statusRowHeight - 10}" rx="3" class="ai-status-charge"/>` : ""}${cheap ? `<rect x="${cellX.toFixed(1)}" y="${(statusTop + statusRowHeight * 2 + 5).toFixed(1)}" width="${cellWidth.toFixed(1)}" height="${statusRowHeight - 10}" rx="3" class="ai-status-tariff"/>` : ""}`;
    }).join("");
    const statusGrid = [0, 1, 2, 3].map((index) => `<line x1="${left}" y1="${statusTop + index * statusRowHeight}" x2="${width - right}" y2="${statusTop + index * statusRowHeight}" class="ai-status-grid"/>`).join("");
    const statusVertical = values.map((row, index) => index % gridInterval === 0 ? `<line x1="${x(index).toFixed(1)}" y1="${statusTop}" x2="${x(index).toFixed(1)}" y2="${statusTop + statusRowHeight * 3}" class="ai-status-grid ai-status-grid-v"/>` : "").join("");
    const firstDate = values[0]?.date || "";
    const secondDate = values[24]?.date || "";
    const daySeparator = is48h ? `<line x1="${(left + step * 24).toFixed(1)}" y1="${top - 18}" x2="${(left + step * 24).toFixed(1)}" y2="${statusTop + statusRowHeight * 3}" class="ai-readable-day-separator"/><text x="${left + step * 12}" y="${top - 25}" text-anchor="middle" class="ai-readable-day-label">Dziś · ${this.escapeHtml(firstDate)}</text><text x="${left + step * 36}" y="${top - 25}" text-anchor="middle" class="ai-readable-day-label">Jutro · ${this.escapeHtml(secondDate)}</text>` : "";
    const currentIndex = values.findIndex((row) => row.date === this.localDateKey(now) && Number(row.hour) === now.getHours());
    const nowX = currentIndex < 0 ? null : left + step * (currentIndex + now.getMinutes() / 60);
    const currentLine = nowX === null ? "" : `<line x1="${nowX.toFixed(1)}" y1="${top}" x2="${nowX.toFixed(1)}" y2="${statusTop + statusRowHeight * 3}" class="ai-readable-now"/><rect x="${(nowX + 6).toFixed(1)}" y="${top + 5}" width="42" height="20" rx="4" class="ai-readable-now-tag"/><text x="${(nowX + 27).toFixed(1)}" y="${top + 19}" text-anchor="middle" class="ai-readable-now-text">Teraz</text>`;
    const chartId = `readable-${String(title).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    const display = (value, digits = 2, unit = "") => {
      const number = this.asNumber(value);
      return number === null ? "brak danych" : `${number.toFixed(digits)}${unit}`;
    };
    const tips = values.map((row, index) => {
      const actualRow = actual[index];
      const forecast = weatherMap.get(`${row.date}-${row.hour}`) || {};
      const [, condition] = this.aiWeatherMeta(forecast.condition);
      return `<div class="ai-chart-tip-source" data-ai-tip-source="${chartId}-${index}"><strong>${this.escapeHtml(String(row.date || ""))} · ${this.escapeHtml(String(row.label || this.hourLabel(row.hour)))}</strong><div><span>Produkcja rzeczywista</span><b>${actualRow?.pvSamples ? display(actualRow.pv, 2, " kWh") : "brak danych"}</b><span>Zużycie</span><b>${actualRow?.loadSamples ? display(actualRow.load, 2, " kWh") : display(row.load_kwh, 2, " kWh")}</b><span>Prognoza Solcast</span><b>${display(row.solcast_kwh, 2, " kWh")}</b><span>Prognoza skorygowana</span><b>${display(row.corrected_pv_kwh, 2, " kWh")}</b><span>Przedział prognozy</span><b>${display(row.forecast_low_kwh, 2)}–${display(row.forecast_high_kwh, 2, " kWh")}</b><span>SOC</span><b>${display(row.soc_after, 1, "%")}</b><span>Status</span><b>${row.action === "sell" ? "sprzedaż" : row.action === "charge" ? "ładowanie" : "bez zmiany"}</b><span>Dystrybucja</span><b>${display(row.distribution, 4, " PLN/kWh")}</b><span>Pogoda</span><b>${forecast.condition ? `${this.escapeHtml(condition)} · ${display(forecast.temperature, 1, "°C")}` : "brak danych"}</b><span>Opady</span><b>${display(forecast.precipitation_probability, 0, "%")}</b><span>Bilans</span><b>${display(row.balance_pln, 2, " PLN")}</b></div></div>`;
    }).join("");
    const hits = values.map((row, index) => `<rect x="${(left + index * step).toFixed(1)}" y="${top}" width="${Math.max(1, step).toFixed(1)}" height="${statusTop + statusRowHeight * 3 - top}" class="ai-chart-hit" data-ai-chart-point="${chartId}" data-ai-chart-index="${index}"/>`).join("");
    const legend = [
      ["load", "Zużycie"], ["actual", "Produkcja rzeczywista"], ["solcast", "Prognoza Solcast"],
      ["corrected", "Prognoza skorygowana"], ["band", "Przedział prognozy"], ["soc", "SOC (%)"], ["minimum", `Min. SOC ${minSoc === null ? "" : `${minSoc.toFixed(0)}%`}`],
    ].map(([key, label]) => `<button class="${hidden.has(key) ? "disabled" : ""} ${key}" data-ai-chart-series="${key}" type="button"><i></i>${label}</button>`).join("");
    return `<section class="ai-chart-card ai-readable-chart" data-ai-chart="${chartId}"><h3>${this.escapeHtml(title)}</h3><div class="ai-readable-legend">${legend}</div><div class="ai-chart-scroll"><svg viewBox="0 0 ${width} ${height}" style="min-width:${width}px" role="img" aria-label="${this.escapeHtml(title)}"><text x="${left - 40}" y="${top - 16}" class="ai-readable-unit">kWh</text><text x="${width - right + 24}" y="${top - 16}" class="ai-readable-unit">%</text>${horizontalGrid}${verticalGrid}${band}${bars}${solcastLine}${correctedLine}${socLine}${minSocLine}<line x1="${left}" y1="${top + plotHeight}" x2="${width - right}" y2="${top + plotHeight}" class="ai-readable-baseline"/>${xLabels}<text x="12" y="${weatherIconY}" class="ai-readable-section-label">Pogoda</text>${weather}${statusGrid}${statusVertical}<text x="12" y="${statusTop - 10}" class="ai-readable-section-label">Status godziny</text><text x="15" y="${statusTop + 21}" class="ai-status-label sell">■ Sprzedaż</text><text x="15" y="${statusTop + statusRowHeight + 21}" class="ai-status-label charge">■ Ładowanie</text><text x="15" y="${statusTop + statusRowHeight * 2 + 21}" class="ai-status-label tariff">■ Tania dystrybucja</text>${statuses}${daySeparator}${currentLine}<line class="ai-chart-crosshair-x" x1="0" x2="0" y1="${top}" y2="${statusTop + statusRowHeight * 3}"/><line class="ai-chart-crosshair-y" x1="${left}" x2="${width - right}" y1="0" y2="0"/>${hits}</svg></div><div class="ai-chart-tooltip" data-ai-chart-tooltip></div>${tips}<small class="ai-chart-help">Kliknij legendę, aby ukryć serię. Najedź kursorem lub dotknij godziny, aby zobaczyć energię, SOC, pogodę i status.</small></section>`;
  }

  aiReadableEnergyChart(rows, title = "Plan energii") {
    const values = Array.isArray(rows) ? rows : [];
    if (values.length <= 24) return this.aiReadableDayChart(values, title, "single");

    const days = [];
    values.slice(0, 48).forEach((row) => {
      const date = row?.date || "brak daty";
      let day = days.find((item) => item.date === date);
      if (!day) {
        day = { date, rows: [] };
        days.push(day);
      }
      day.rows.push(row);
    });
    return `<section class="ai-energy-48-crisp"><h3>${this.escapeHtml(title)}</h3><div class="ai-readable-stack">${days.slice(0, 2).map((day, index) => this.aiReadableDayChart(day.rows, `${index === 0 ? "Dziś" : "Jutro"} · ${day.date}`, `day-${index}`)).join("")}</div></section>`;
  }

  aiReadableDayChart(rows, title, chartSuffix = "single") {
    const values = Array.isArray(rows) ? rows.slice(0, 24) : [];
    const count = Math.max(1, values.length);
    const width = 1000;
    const top = 10;
    const plotHeight = 252;
    const bottom = top + plotHeight;
    const step = width / count;
    const hidden = this._aiChartHiddenSeries instanceof Set ? this._aiChartHiddenSeries : new Set();
    const visible = (name) => !hidden.has(name);
    const history = this.aiHistoricalHours();
    const now = new Date();
    const todayKey = this.localDateKey(now);
    const actual = values.map((row) => {
      if (row.date !== todayKey || Number(row.hour) > now.getHours()) return null;
      return history.get(`${row.date}-${row.hour}`) || null;
    });
    const actualSource = (row, actualRow) => {
      if (row.date !== todayKey || Number(row.hour) > now.getHours()) return "Brak danych — godzina przyszła";
      if (Number(row.hour) === now.getHours()) return actualRow?.pvSamples ? "Bieżące — godzina częściowa" : "Brak danych";
      return actualRow?.pvSamples ? "Rzeczywiste" : "Brak danych";
    };
    const weatherState = this._hass?.states?.[this.entity("sensor", "ai_state")]?.attributes?.weather || {};
    const forecastRows = Array.isArray(weatherState.forecast) ? weatherState.forecast : [];
    const weatherMap = new Map(forecastRows.map((row) => {
      const stamp = new Date(row?.datetime ?? row?.time ?? "");
      return Number.isNaN(stamp.getTime()) ? ["", null] : [`${this.localDateKey(stamp)}-${stamp.getHours()}`, row];
    }));
    const energyValues = [];
    values.forEach((row, index) => {
      [actual[index]?.pvSamples ? actual[index].pv : null, actual[index]?.loadSamples ? actual[index].load : null,
        this.asNumber(row.load_kwh), this.asNumber(row.solcast_kwh), this.asNumber(row.corrected_pv_kwh), this.asNumber(row.forecast_high_kwh)]
        .forEach((value) => { if (value !== null) energyValues.push(Math.max(0, value)); });
    });
    const maxEnergy = Math.max(1, ...energyValues) * 1.08;
    const x = (index) => index * step + step / 2;
    const yEnergy = (value) => bottom - Math.max(0, value || 0) / maxEnergy * plotHeight;
    const ySoc = (value) => bottom - Math.max(0, Math.min(100, value || 0)) / 100 * plotHeight;
    const linePoints = (field, yFn) => values.map((row, index) => {
      const value = this.asNumber(row[field]);
      return value === null ? null : `${x(index).toFixed(1)},${yFn(value).toFixed(1)}`;
    }).filter(Boolean).join(" ");
    const horizontalGrid = [.2, .4, .6, .8].map((part) => `<line x1="0" y1="${(top + plotHeight * part).toFixed(1)}" x2="${width}" y2="${(top + plotHeight * part).toFixed(1)}" class="ai-crisp-grid"/>`).join("");
    const verticalGuides = [0, 6, 12, 18, 24].map((hour) => `<line x1="${(hour * step).toFixed(1)}" y1="${top}" x2="${(hour * step).toFixed(1)}" y2="${bottom}" class="ai-crisp-guide"/>`).join("");
    const bars = values.map((row, index) => {
      const actualRow = actual[index];
      const load = actualRow?.loadSamples ? actualRow.load : this.asNumber(row.load_kwh);
      const production = actualRow?.pvSamples ? actualRow.pv : null;
      const draw = (value, offset, css) => value === null ? "" : `<rect x="${(x(index) + step * offset - Math.max(2, step * .13)).toFixed(1)}" y="${yEnergy(value).toFixed(1)}" width="${Math.max(4, step * .26).toFixed(1)}" height="${Math.max(0, bottom - yEnergy(value)).toFixed(1)}" rx="2" class="${css}"/>`;
      return `${visible("load") ? draw(load, -.17, "ai-crisp-load") : ""}${visible("actual") ? draw(production, .17, "ai-crisp-actual") : ""}`;
    }).join("");
    const upper = values.map((row, index) => {
      const value = this.asNumber(row.forecast_high_kwh);
      return value === null ? null : `${x(index).toFixed(1)},${yEnergy(value).toFixed(1)}`;
    }).filter(Boolean);
    const lower = values.map((row, index) => {
      const value = this.asNumber(row.forecast_low_kwh);
      return value === null ? null : `${x(index).toFixed(1)},${yEnergy(value).toFixed(1)}`;
    }).filter(Boolean).reverse();
    const band = visible("band") && upper.length && lower.length ? `<polygon points="${[...upper, ...lower].join(" ")}" class="ai-crisp-band"/>` : "";
    const solcastLine = visible("solcast") ? `<polyline points="${linePoints("solcast_kwh", yEnergy)}" class="ai-crisp-solcast"/>` : "";
    const correctedLine = visible("corrected") ? `<polyline points="${linePoints("corrected_pv_kwh", yEnergy)}" class="ai-crisp-corrected"/>` : "";
    const socLine = visible("soc") ? `<polyline points="${linePoints("soc_after", ySoc)}" class="ai-crisp-soc"/>` : "";
    const minSoc = this.asNumber(values[0]?.hard_min_soc_pct ?? this.aiSettings()?.minSoc);
    const effectiveMinSoc = this.asNumber(values[0]?.effective_min_soc_pct ?? minSoc);
    const sameMinimum = minSoc !== null
      && effectiveMinSoc !== null
      && Math.abs(effectiveMinSoc - minSoc) <= .05;
    const minSocLine = visible("minimum") && minSoc !== null ? `<line x1="0" y1="${ySoc(minSoc).toFixed(1)}" x2="${width}" y2="${ySoc(minSoc).toFixed(1)}" class="ai-crisp-min-soc"/>` : "";
    const effectiveMinSocLine = visible("effective-minimum") && effectiveMinSoc !== null && !sameMinimum ? `<line x1="0" y1="${ySoc(effectiveMinSoc).toFixed(1)}" x2="${width}" y2="${ySoc(effectiveMinSoc).toFixed(1)}" class="ai-crisp-effective-min-soc"/>` : "";
    const currentIndex = values.findIndex((row) => row.date === this.localDateKey(now) && Number(row.hour) === now.getHours());
    const currentX = currentIndex < 0 ? null : (currentIndex + now.getMinutes() / 60) * step;
    const currentPercent = currentX === null
      ? null
      : Math.max(3, Math.min(97, currentX / width * 100)).toFixed(2);
    const currentLine = currentX === null ? "" : `<line x1="${currentX.toFixed(1)}" y1="${top}" x2="${currentX.toFixed(1)}" y2="${bottom}" class="ai-crisp-now"/>`;
    const distribution = values.map((row) => this.asNumber(row.distribution)).filter((value) => value !== null && value > 0);
    const cheapRate = distribution.length ? Math.min(...distribution) : null;
    const timeLabels = values.map((row, index) => `<span>${index % 3 === 0 ? `${String(row.hour).padStart(2, "0")}:00` : ""}</span>`).join("");
    const weatherCells = values.map((row) => {
      const forecast = weatherMap.get(`${row.date}-${row.hour}`);
      const [icon, label] = forecast ? this.aiWeatherMeta(forecast.condition) : ["—", "brak prognozy"];
      const precipitation = this.asNumber(forecast?.precipitation_probability);
      const risk = precipitation === null ? "missing" : precipitation >= 70 ? "high" : precipitation >= 35 ? "medium" : "low";
      return `<span class="ai-crisp-weather-cell" title="${this.escapeHtml(`${label}${precipitation === null ? "" : ` · opady ${precipitation.toFixed(0)}%`}`)}"><b>${icon}</b><i class="${risk}"></i></span>`;
    }).join("");
    const statusCells = (kind) => values.map((row) => {
      const rate = this.asNumber(row.distribution);
      const matches = kind === "sell" ? row.action === "sell" : kind === "charge" ? row.action === "charge" : cheapRate !== null && rate !== null && rate <= cheapRate + .00001;
      const active = visible(kind) && matches;
      return `<span class="${active ? `active ${kind}` : `inactive ${kind}`}"></span>`;
    }).join("");
    const chartId = `crisp-${String(chartSuffix).replace(/[^a-z0-9]+/gi, "-")}-${String(values[0]?.date || "empty").replace(/[^a-z0-9]+/gi, "-")}`;
    const display = (value, digits = 2, unit = "") => {
      const number = this.asNumber(value);
      return number === null ? "brak danych" : `${this.aiFormatNumber(number, digits)}${unit}`;
    };
    const tips = values.map((row, index) => {
      const actualRow = actual[index];
      const forecast = weatherMap.get(`${row.date}-${row.hour}`) || {};
      const [, condition] = this.aiWeatherMeta(forecast.condition);
      return `<div class="ai-chart-tip-source" data-ai-tip-source="${chartId}-${index}"><strong>${this.aiFormatDate(row.date)} · ${this.escapeHtml(String(row.label || this.hourLabel(row.hour)))}</strong><div><span>Produkcja rzeczywista</span><b>${actualRow?.pvSamples ? display(actualRow.pv, 2, " kWh") : "brak danych"}</b><span>Źródło punktu</span><b>${this.escapeHtml(actualSource(row, actualRow))}</b><span>Zużycie</span><b>${actualRow?.loadSamples ? display(actualRow.load, 2, " kWh") : display(row.load_kwh, 2, " kWh")}</b><span>Prognoza Solcast</span><b>${display(row.solcast_kwh, 2, " kWh")}</b><span>Prognoza skorygowana</span><b>${display(row.corrected_pv_kwh, 2, " kWh")}</b><span>Przedział prognozy</span><b>${display(row.forecast_low_kwh, 2)}–${display(row.forecast_high_kwh, 2, " kWh")}</b><span>SOC</span><b>${display(row.soc_after, 1, "%")}</b><span>Min. SOC użytkownika</span><b>${display(minSoc, 1, "%")}</b><span>Efektywne minimum planu</span><b title="Plan zatrzymał rozładowanie wcześniej, aby zachować dodatkową rezerwę energii.">${display(effectiveMinSoc, 1, "%")}</b><span>Status</span><b>${this.escapeHtml(this.aiActionLabel(row.action))}</b><span>Pogoda</span><b>${forecast.condition ? `${this.escapeHtml(condition)} · ${display(forecast.temperature, 1, "°C")}` : "brak danych"}</b><span>Bilans</span><b>${display(row.balance_pln, 2, " zł")}</b></div></div>`;
    }).join("");
    const hits = values.map((row, index) => `<rect x="${(index * step).toFixed(1)}" y="${top}" width="${Math.max(1, step).toFixed(1)}" height="${plotHeight}" class="ai-chart-hit ai-crisp-hit" data-ai-chart-point="${chartId}" data-ai-chart-index="${index}"/>`).join("");
    const minimumLabel = sameMinimum
      ? `Minimum SOC ${this.aiFormatNumber(minSoc, 1)}% (użytkownik = plan)`
      : `Min. SOC użytkownika ${minSoc === null ? "" : `${this.aiFormatNumber(minSoc, 1)}%`}`;
    const legendItems = [
      ["load", "Zużycie"],
      ["actual", "Produkcja rzeczywista"],
      ["solcast", "Prognoza Solcast"],
      ["corrected", "Prognoza skorygowana"],
      ["band", "Przedział prognozy"],
      ["soc", "SOC (%)"],
      ["minimum", minimumLabel],
      sameMinimum ? null : ["effective-minimum", `Efektywne minimum planu ${effectiveMinSoc === null ? "" : `${this.aiFormatNumber(effectiveMinSoc, 1)}%`}`],
      ["sell", "Sprzedaż"],
      ["charge", "Ładowanie"],
      ["tariff", "Tania taryfa"],
    ].filter(Boolean);
    const legend = legendItems.map(([key, label]) => `<button class="${hidden.has(key) ? "disabled" : ""} ${key}" data-ai-chart-series="${key}" type="button"><i></i>${label}</button>`).join("");
    const leftAxis = [maxEnergy, maxEnergy / 2, 0].map((value) => `<span>${this.aiFormatNumber(value, 1)}</span>`).join("");
    return `<section class="ai-chart-card ai-crisp-chart" data-ai-chart="${chartId}"><h3>${this.escapeHtml(title)}</h3><div class="ai-crisp-legend">${legend}</div><div class="ai-crisp-layout"><div class="ai-crisp-axis ai-crisp-axis-left"><b>kWh</b><div class="ai-crisp-axis-values">${leftAxis}</div></div><div class="ai-crisp-main"><div class="ai-crisp-plot"><svg class="ai-crisp-svg" viewBox="0 0 ${width} ${bottom}" preserveAspectRatio="none" role="img" aria-label="${this.escapeHtml(title)}">${horizontalGrid}${verticalGuides}${band}${bars}${solcastLine}${correctedLine}${socLine}${minSocLine}${effectiveMinSocLine}${currentLine}<line x1="0" y1="${bottom}" x2="${width}" y2="${bottom}" class="ai-crisp-baseline"/><line class="ai-chart-crosshair-x" x1="0" x2="0" y1="${top}" y2="${bottom}"/><line class="ai-chart-crosshair-y" x1="0" x2="${width}" y1="0" y2="0"/>${hits}</svg>${currentX === null ? "" : `<span class="ai-crisp-now-tag" style="left:${currentPercent}%">Teraz</span>`}</div><div class="ai-crisp-integrated-grid"><div class="ai-crisp-weather-grid">${weatherCells}</div><div class="ai-crisp-status"><div class="sell" title="Sprzedaż">${statusCells("sell")}</div><div class="charge" title="Ładowanie">${statusCells("charge")}</div><div class="tariff" title="Tania taryfa">${statusCells("tariff")}</div></div><div class="ai-crisp-time-grid">${timeLabels}</div></div></div><div class="ai-crisp-axis ai-crisp-axis-right"><b>%</b><div class="ai-crisp-axis-values"><span>100</span><span>50</span><span>0</span></div></div></div><div class="ai-chart-tooltip" data-ai-chart-tooltip></div>${tips}<small class="ai-chart-help">Oś energii zaczyna się od 0 kWh, a oś SOC ma zakres 0–100%. Pogoda, działania i taryfa są wyrównane do tych samych 24 kolumn godzinowych. Dla przyszłych godzin produkcja rzeczywista nie jest rysowana.</small></section>`;
  }

  aiApiPresentation(planner = null) {
    const api = this.aiApiContext() || {};
    const error = String(api.last_error || api.error || "");
    const authError = /(?:401|invalid token|unauthori[sz]ed|autoryzac)/i.test(error);
    if (authError) return {
      status: "Asystent AI: błąd autoryzacji",
      message: "Sprawdź klucz API dostawcy.",
      detail: "HTTP 401 — nieprawidłowy klucz lub token",
      external: false,
    };
    if (error) return {
      status: "Asystent AI: błąd połączenia",
      message: "Lokalny plan pozostaje dostępny.",
      detail: error.replace(/\{.*$/s, "").trim(),
      external: false,
    };
    const rawStatus = String(api.status || (api.config?.enabled ? "ready" : "disabled")).toLowerCase();
    const sourceMatches = !planner || (
      String(api.last_plan_id || "") === String(planner.plan_id || "")
      && String(api.last_input_snapshot_id || "") === String(planner.input_snapshot_id || "")
    );
    const external = ["ok", "success", "completed"].includes(rawStatus) && !!api.last_analysis && sourceMatches;
    if (!!api.last_analysis && !sourceMatches) return {
      status: "Asystent AI: wyjaśnienie nieaktualne",
      message: "Optimizer Core przeliczył plan po tej odpowiedzi. Wyświetlane są wyłącznie aktualne dane lokalne.",
      detail: "Niezgodny plan_id lub input_snapshot_id",
      external: false,
      stale: true,
      provider: api.provider,
      model: api.model,
    };
    const statusLabels = {
      disabled: "Asystent AI: wyłączony",
      ready: "Asystent AI: gotowy",
      waiting: "Asystent AI: oczekuje",
      testing: "Asystent AI: testowanie połączenia",
      busy: "Asystent AI: analizuje",
      analysing: "Asystent AI: analizuje",
      analyzing: "Asystent AI: analizuje",
      connected: "Asystent AI: połączony",
      ok: "Asystent AI: analiza zakończona",
      success: "Asystent AI: analiza zakończona",
      completed: "Asystent AI: analiza zakończona",
      rejected: "Asystent AI: odpowiedź odrzucona",
    };
    return {
      status: statusLabels[rawStatus] || `Asystent AI: ${this.aiUiText(rawStatus)}`,
      message: external ? "Odpowiedź zewnętrzna jest dostępna." : "Plan jest wyjaśniany lokalnie przez Optimizer Core.",
      detail: "",
      external,
      provider: api.provider,
      model: api.model,
      summary: external ? String(api.last_analysis?.summary || "") : "",
      candidateValidated: api.candidate?.accepted_by_core === true,
    };
  }

  aiPlanStatus(planner, future) {
    const results = Object.values(future?.slot_results || {}).filter((item) => item && typeof item === "object");
    const count = (status) => results.filter((item) => item.status === status).length;
    const total = Array.isArray(future?.updates) ? future.updates.length : 0;
    const details = [
      count("confirmed") ? `potwierdzone ${count("confirmed")}` : "",
      count("physical_pending") ? `oczekuje na falownik ${count("physical_pending")}` : "",
      count("logical_applied") ? `zapisane logicznie ${count("logical_applied")}` : "",
      count("waiting_data") ? `oczekuje na dane ${count("waiting_data")}` : "",
      count("missed") ? `pominięte ${count("missed")}` : "",
      count("blocked") ? `zablokowane ${count("blocked")}` : "",
      count("manual_override") ? `zastąpione ręcznie ${count("manual_override")}` : "",
    ].filter(Boolean).join(" · ");
    if (["scheduled", "partial", "confirmed", "legacy_unconfirmed"].includes(future?.status)) {
      return `Plan ${this.aiUiText(future.status)} na ${this.aiFormatDate(future.date)} · ${total} slotów${details ? ` · ${details}` : ""}`;
    }
    if (planner.plan_status === "blocked") return "Plan zablokowany";
    const tomorrow = String(planner?.ui_insights?.tomorrow_plan_status || "");
    if (tomorrow) return this.aiUiText(tomorrow);
    const hasTomorrow = (planner.rows || []).some((row) => row.day === "tomorrow" && row.proposed);
    return hasTomorrow ? "Plan na jutro utworzony — oczekuje na zatwierdzenie" : "Prognoza utworzona";
  }

  renderAiExplanation(planner) {
    const profiles = this.aiSaleInsights(planner);
    const publication = planner.ui_insights?.price_publication || {};
    const api = this.aiApiPresentation(planner);
    const day = this._aiExplanationDay === "tomorrow" ? "tomorrow" : "today";
    const dayLabel = day === "today" ? "Dziś" : "Jutro";
    const plannerRows = this.aiRowsForDay(planner, day);
    const optimizerRows = plannerRows
      .filter((row) => this.aiIsApplicableProposal(row) && row.action === "sell" && !this.aiProfileId(row))
      .sort((a, b) => Number(a.hour) - Number(b.hour));
    const dateValue = plannerRows[0]?.date
      || profiles.morning_sale?.day_summaries?.[day]?.date
      || profiles.evening_sale?.day_summaries?.[day]?.date;
    const optimizerEnergy = optimizerRows.reduce((sum, row) => sum + (this.asNumber(row.planned_energy_kwh ?? row.energy_kwh) || 0), 0);
    const profileEnergy = Object.values(profiles).reduce((sum, profile) => {
      const summary = profile?.day_summaries?.[day];
      if (summary) return sum + (this.asNumber(summary.profile_planned_energy_kwh) || 0);
      const compact = Array.isArray(profile?.days?.[day]) ? profile.days[day] : [];
      return sum + compact.filter((row) => row.recommended).reduce((acc, row) => acc + (this.asNumber(row.planned_energy_kwh) || 0), 0);
    }, 0);
    const explainProfile = (profileId, defaultLabel) => {
      const profile = profiles[profileId] || {};
      if (!profile.enabled) return "";
      const target = this.asNumber(profile.target_energy_kwh) || 0;
      const rows = Array.isArray(profile.days?.[day]) ? profile.days[day] : [];
      const selected = rows.filter((row) => row.recommended).sort((a, b) => Number(a.hour) - Number(b.hour));
      const omitted = rows.filter((row) => !row.recommended).sort((a, b) => Number(a.hour) - Number(b.hour));
      const fallbackPlanned = selected.reduce((sum, row) => sum + (this.asNumber(row.planned_energy_kwh) || 0), 0);
      const summary = profile.day_summaries?.[day] || {
        ...(profile.explanation || {}),
        target_energy_kwh: target,
        profile_planned_energy_kwh: fallbackPlanned,
        optimizer_extra_energy_kwh: 0,
        total_proposed_energy_kwh: fallbackPlanned,
        missing_profile_energy_kwh: Math.max(0, target - fallbackPlanned),
        primary_constraint: profile.explanation?.primary_constraint,
      };
      const dailyTarget = this.asNumber(summary.target_energy_kwh) ?? target;
      const planned = this.asNumber(summary.profile_planned_energy_kwh) || 0;
      const extra = this.asNumber(summary.optimizer_extra_energy_kwh) || 0;
      const total = this.asNumber(summary.total_proposed_energy_kwh) ?? planned + extra;
      const missing = this.asNumber(summary.missing_profile_energy_kwh) ?? Math.max(0, dailyTarget - planned);
      const selectedRows = selected.map((row) => {
        const source = plannerRows.find((item) => item.date === row.date && Number(item.hour) === Number(row.hour) && this.aiProfileId(item) === profileId) || row;
        const priceRank = this.asNumber(row.price_rank);
        const basis = source.power_basis || row.limit_reasons?.[0] || "profile_energy_allocation";
        const power = this.aiPlannedSlotPower(source) || this.aiPlannedSlotPower(row);
        const requested = this.asNumber(source.requested_action_energy_kwh ?? row.requested_energy_kwh);
        const powerLimit = this.asNumber(source.power_limit_w ?? row.power_limit_w);
        return `<li><strong>${dayLabel} · ${this.aiFormatDate(row.date)} · ${this.escapeHtml(row.label || this.hourLabel(row.hour))}</strong><span>Cena ${this.aiFormatNumber(row.sell_price, 2)} zł/kWh${priceRank === null ? "" : ` · pozycja ${priceRank} w tym dniu`}. Zaplanowano ${this.aiFormatNumber(source.planned_energy_kwh ?? row.planned_energy_kwh, 2)} kWh przy mocy <b>${power} W</b>. Źródło: profil użytkownika. Ograniczenie wiążące: ${this.escapeHtml(this.aiUiText(basis))}.${requested === null ? "" : ` Żądana energia: ${this.aiFormatNumber(requested, 2)} kWh.`}${powerLimit === null ? "" : ` Limit mocy: ${this.aiFormatNumber(powerLimit, 0)} W.`} SOC ${this.aiFormatNumber(source.soc_start_pct ?? row.soc_before, 1)}% → ${this.aiFormatNumber(source.soc_end_pct ?? row.soc_after, 1)}%.</span></li>`;
      }).join("") || "<li>Brak godzin wybranych do sprzedaży w tym dniu.</li>";
      const omittedRows = omitted.map((row) => `<li><strong>${dayLabel} · ${this.aiFormatDate(row.date)} · ${this.escapeHtml(row.label || this.hourLabel(row.hour))}</strong><span>${this.escapeHtml(this.aiUiText(row.skip_reason || "not_selected_by_energy_budget"))}; cena ${this.aiFormatNumber(row.sell_price, 2)} zł/kWh${this.asNumber(row.price_rank) === null ? "" : ` · pozycja ${this.aiFormatNumber(row.price_rank, 0)} w tym dniu`}.</span></li>`).join("") || "<li>Brak pominiętych godzin w oknie profilu dla wybranego dnia.</li>";
      const primaryCode = summary.primary_constraint || (missing > .001 ? "unresolved_daily_constraint" : "target_reached");
      const primary = this.aiUiText(primaryCode);
      const ended = primaryCode === "past_window" || summary.window_ended;
      const decisionSummary = ended
        ? "Dzisiejsze okno porannej sprzedaży już się zakończyło. Kolejna ocena profilu dotyczy jutra."
        : `Profil użytkownika zaplanował <b>${this.aiFormatNumber(planned, 2)} kWh</b> z celu <b>${this.aiFormatNumber(dailyTarget, 2)} kWh</b>. Sugestie optymalizatora w tym oknie: <b>${this.aiFormatNumber(extra, 2)} kWh</b>; pełna propozycja dnia: <b>${this.aiFormatNumber(total, 2)} kWh</b>. ${missing > .001 ? `Do celu profilu nadal brakuje <b>${this.aiFormatNumber(missing, 2)} kWh</b>.` : "Cel profilu został osiągnięty."} Główna przyczyna: <b>${this.escapeHtml(primary)}</b>.`;
      return `<section class="ai-explanation-profile ai-metric-card"><h3>${this.escapeHtml(profile.name || defaultLabel)} · ${dayLabel}${summary.date ? ` · ${this.aiFormatDate(summary.date)}` : ""}</h3><p class="ai-decision-summary">${decisionSummary}</p><div class="ai-explanation-balance"><div><span>Cel profilu</span><strong>${this.aiFormatNumber(dailyTarget, 2)} kWh</strong></div><div><span>Plan profilu</span><strong>${this.aiFormatNumber(planned, 2)} kWh</strong></div><div><span>Dodatkowo optymalizator</span><strong>${this.aiFormatNumber(extra, 2)} kWh</strong></div><div><span>Pełna propozycja</span><strong>${this.aiFormatNumber(total, 2)} kWh</strong></div><div><span>Brakuje do celu profilu</span><strong>${this.aiFormatNumber(missing, 2)} kWh</strong></div><div><span>SOC na początku okna</span><strong>${this.aiFormatNumber(summary.initial_soc_pct, 1)}%</strong></div><div><span>Minimalny SOC</span><strong>${this.aiFormatNumber(summary.minimum_soc_pct ?? profile.minimum_soc_after, 1)}%</strong></div><div><span>Energia użyteczna na początku</span><strong>${this.aiFormatNumber(summary.usable_energy_at_window_start_kwh, 2)} kWh</strong></div><div><span>Prognoza domu / PV w oknie</span><strong>${this.aiFormatNumber(summary.forecast_home_in_window_kwh, 2)} / ${this.aiFormatNumber(summary.forecast_pv_in_window_kwh, 2)} kWh</strong></div></div><p class="ai-note">Energia dodatkowych sugestii optymalizatora nie jest zaliczana jako wykonanie celu profilu użytkownika.</p><details open><summary>Dlaczego wybrano te godziny i moce?</summary><ul class="ai-explanation-list">${selectedRows}</ul></details><details><summary>Dlaczego pominięto pozostałe godziny?</summary><ul class="ai-explanation-list">${omittedRows}</ul></details><details><summary>Co może zmienić plan?</summary><p>Większy SOC lub produkcja PV mogą zwiększyć dostępną energię. Większe zużycie domu, wyższa rezerwa SOC albo ograniczenia falownika mogą ją zmniejszyć. Zmiana cen może przenieść energię do korzystniejszych godzin. Informacja ta nie zmienia zabezpieczeń ani ustawień Deye.</p></details></section>`;
    };
    const optimizerCard = optimizerRows.length ? `<section class="ai-metric-card ai-explanation-profile"><h3>Dodatkowe sugestie optymalizatora · ${dayLabel}</h3><p class="ai-note">Te godziny wynikają z lokalnej optymalizacji całego dnia i nie są zaliczane do celu energii profilu użytkownika.</p><ul class="ai-explanation-list">${optimizerRows.map((row) => {
      const basis = row.power_basis || row.limit_reason || "optimizer_energy_allocation";
      return `<li><strong>${dayLabel} · ${this.aiFormatDate(row.date)} · ${this.escapeHtml(row.label || this.hourLabel(row.hour))}</strong><span>Cena ${this.aiFormatNumber(row.sell_price, 2)} zł/kWh. Zaplanowano ${this.aiFormatNumber(row.planned_energy_kwh, 2)} kWh przy mocy <b>${this.aiPlannedSlotPower(row)} W</b>. Źródło: lokalny optymalizator. Ograniczenie wiążące: ${this.escapeHtml(this.aiUiText(basis))}. SOC ${this.aiFormatNumber(row.soc_start_pct, 1)}% → ${this.aiFormatNumber(row.soc_end_pct, 1)}%.</span></li>`;
    }).join("")}</ul></section>` : "";
    const shadow = planner.optimizer_shadow || {};
    const shadowCard = shadow.mode === "comparison_only" ? `<details class="ai-metric-card ai-shadow"><summary>Porównanie diagnostyczne optimizer shadow</summary><div class="ai-kpis"><div><span>Plan podstawowy</span><strong>${this.formatSignedMoney(shadow.legacy_result)}</strong></div><div><span>Kandydat shadow</span><strong>${this.formatSignedMoney(shadow.candidate_result)}</strong></div><div><span>Różnica</span><strong>${this.formatSignedMoney(shadow.candidate_delta)}</strong></div><div><span>Zmienione sloty</span><strong>${Array.isArray(shadow.changed_slots) ? shadow.changed_slots.length : 0}</strong></div></div><p class="ai-note">Porównanie jest tylko diagnostyczne. Nie zapisuje ustawień i zawsze wymaga ręcznego potwierdzenia.</p></details>` : "";
    const publicationText = publication.tomorrow_status === "complete"
      ? "Ceny na jutro są kompletne — sprzedaż i zakup 24/24."
      : publication.tomorrow_status === "awaiting_publication"
        ? `Ceny na jutro nie zostały jeszcze opublikowane. Oczekiwana publikacja po ${publication.expected_tomorrow_after_hour || 13}:00; plan jutra jest tymczasowy i zostanie przeliczony po zmianie danych.`
        : `Ceny na jutro są nadal niekompletne po progu bezpieczeństwa ${publication.warning_after_hour || 14}:${String(publication.warning_after_minute ?? 30).padStart(2, "0")}. Sprawdź źródła cen; plan jutra pozostaje zablokowany.`;
    return `<div class="ai-explanation-view"><h2>Dlaczego ten plan?</h2><div class="ai-proposal-toolbar"><div class="ai-day-tabs"><button class="${day === "today" ? "active" : ""}" data-ai-explanation-day="today">Dziś</button><button class="${day === "tomorrow" ? "active" : ""}" data-ai-explanation-day="tomorrow">Jutro</button></div></div><section class="ai-metric-card ai-analysis-source"><h3>Źródło i aktualność decyzji · ${dayLabel}${dateValue ? ` · ${this.aiFormatDate(dateValue)}` : ""}</h3><div class="ai-kpis"><div><span>Źródło planu</span><strong>Lokalny Optimizer Core</strong></div><div><span>Obliczono</span><strong>${this.formatTimeShort(planner.generated_at)}</strong></div><div><span>Energia profili</span><strong>${this.aiFormatNumber(profileEnergy, 2)} kWh</strong></div><div><span>Dodatkowo optymalizator</span><strong>${this.aiFormatNumber(optimizerEnergy, 2)} kWh</strong></div></div><p>${this.escapeHtml(publicationText)}</p><small>${this.escapeHtml(api.status)}. AI API nie zapisuje automatycznie ustawień Deye.</small></section>${explainProfile("morning_sale", "Poranna sprzedaż")}${explainProfile("evening_sale", "Wieczorna sprzedaż")}${optimizerCard}${shadowCard}<details class="ai-metric-card ai-help"><summary>? Jak czytać plan</summary><dl><dt>SOC</dt><dd>Procent energii zgromadzonej w baterii.</dd><dt>Plan profilu</dt><dd>Energia przydzielona do celu ustawionego przez użytkownika.</dd><dt>Sugestia optymalizatora</dt><dd>Dodatkowa zmiana wybrana z bilansu całego dnia; nie zwiększa realizacji celu profilu.</dd><dt>Ograniczenie wiążące</dt><dd>Czynnik, który faktycznie zatrzymał zwiększanie energii lub mocy danego slotu.</dd><dt>Pewność</dt><dd>Ocena kompletności cen, prognozy, historii, encji i bieżącego SOC.</dd><dt>Optimizer shadow</dt><dd>Wariant porównawczy, który niczego sam nie zapisuje.</dd></dl></details></div>`;
  }

  renderAiProfileSummaries(planner) {
    const profiles = this.aiProfiles().profiles || {};
    const impacts = new Map((planner.profile_impacts || []).map((item) => [item.profile_id, item]));
    const labels = { morning_sale: "Poranna sprzedaż", evening_sale: "Wieczorna sprzedaż", charging: "Ładowanie" };
    return `<div class="ai-profile-cards">${["morning_sale", "evening_sale", "charging"].map((profileId) => {
      const profile = profiles[profileId] || {};
      const impact = impacts.get(profileId) || {};
      const charging = profileId === "charging";
      const energyTarget = charging && profile.target_type !== "energy" ? null : this.asNumber(charging ? profile.target_value : profile.target_energy_kwh);
      const targetText = energyTarget === null ? `${this.aiFormatNumber(profile.target_value, 1)}% SOC` : `${this.aiFormatNumber(energyTarget, 2)} kWh`;
      const planned = this.asNumber(impact.planned_energy_kwh) || 0;
      const actual = this.asNumber(impact.actual_energy_kwh) || 0;
      const backendRemaining = this.asNumber(impact.remaining_energy_kwh ?? impact.missing_energy_kwh);
      const remaining = energyTarget === null
        ? "wyliczane z SOC"
        : `${this.aiFormatNumber(backendRemaining === null ? Math.max(0, energyTarget - actual) : backendRemaining, 2)} kWh`;
      const source = charging ? ({ auto: "PV + sieć według planu", pv: "PV", grid: "sieć", pv_and_grid: "PV + sieć" }[profile.source] || "automatyczne") : "sprzedaż do sieci";
      const reason = impact.block_reason || impact.limit_reason || impact.skip_reason || (profile.enabled ? "brak ograniczenia" : "profil wyłączony");
      return `<article class="ai-profile-card ${profile.enabled ? "enabled" : "disabled"}"><h4>${labels[profileId]}</h4><dl><div><dt>Stan profilu</dt><dd>${profile.enabled ? "włączony" : "wyłączony"}</dd></div><div><dt>Okno</dt><dd>${this.escapeHtml(profile.start || "--:--")}–${this.escapeHtml(profile.end || "--:--")}</dd></div><div><dt>Cel</dt><dd>${targetText}</dd></div><div><dt>Zaplanowano</dt><dd>${this.aiFormatNumber(planned, 2)} kWh</dd></div><div><dt>Wykonano</dt><dd>${this.aiFormatNumber(actual, 2)} kWh</dd></div><div><dt>Pozostało</dt><dd>${remaining}</dd></div><div><dt>Status</dt><dd>${this.escapeHtml(this.aiUiText(impact.status || (profile.enabled ? "pending" : "disabled")))}</dd></div><div><dt>Źródło / kierunek</dt><dd>${this.escapeHtml(source)}</dd></div>${charging ? `<div><dt>Maks. efektywny koszt</dt><dd>${this.aiFormatNumber(profile.max_effective_price, 2)} zł/kWh</dd></div><div><dt>Miejsce na PV</dt><dd>${profile.preserve_pv_room ? `${this.aiFormatNumber(profile.minimum_free_room_kwh, 2)} kWh` : "nie wymagano"}</dd></div>` : ""}<div><dt>Powód ograniczenia</dt><dd>${this.escapeHtml(this.aiUiText(reason))}</dd></div></dl></article>`;
    }).join("")}</div>`;
  }

  aiCompactWeather() {
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const weather = aiState?.attributes?.weather || {};
    const hourly = Array.isArray(weather.forecast) ? weather.forecast : [];
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowKey = this.localDateKey(tomorrow);
    const tomorrowRow = hourly.find((row) => {
      const stamp = new Date(row?.datetime ?? row?.time ?? "");
      return !Number.isNaN(stamp.getTime()) && this.localDateKey(stamp) === tomorrowKey;
    });
    const [todayIcon, todayLabel] = this.aiWeatherMeta(weather.condition);
    const [tomorrowIcon, tomorrowLabel] = this.aiWeatherMeta(tomorrowRow?.condition);
    return `<section class="ai-metric-card ai-weather-compact"><h3>Pogoda i aktualność danych</h3><div><span>${todayIcon} Dziś</span><strong>${this.escapeHtml(todayLabel)} · ${this.aiFormatNumber(weather.temperature, 1)}°C</strong></div><div><span>${tomorrowIcon} Jutro</span><strong>${this.escapeHtml(tomorrowLabel)}${tomorrowRow ? ` · ${this.aiFormatNumber(tomorrowRow.temperature, 1)}°C` : ""}</strong></div><small>Aktualizacja: ${this.formatTimeShort(weather.last_updated)} · ${weather.available ? "dane dostępne" : "brak pełnych danych"}</small></section>`;
  }

  renderAiOverview(_slots, planner) {
    const summaries = new Map((planner.days || []).map((row) => [row.day, row]));
    const dayFinancial = (day, label) => {
      const summary = summaries.get(day) || {};
      const complete = summary.financial_data_complete !== false;
      return `${label}: ${this.formatEnergy(summary.sold_kwh || 0)} eksportu / ${complete ? this.formatSignedMoney(summary.balance_pln) : "wynik częściowy — brak cen"}`;
    };
    const checkpoints = planner.checkpoints || {};
    const future = this._hass?.states?.[this.entity("sensor", "ai_state")]?.attributes?.future_plan || {};
    const proposed = (planner.rows || []).filter((row) => row.proposed);
    const representative = this.aiRepresentativeProposal(proposed);
    const representativeEconomics = this.aiSlotEconomics(representative);
    const confidenceValues = proposed
      .map((row) => this.asNumber(row.effective_confidence ?? row.confidence))
      .filter((value) => value !== null);
    const confidence = confidenceValues.length ? Math.min(...confidenceValues) : null;
    const benefit = this.asNumber(planner.benefit) || 0;
    const threshold = Math.max(0, this.asNumber(planner.neutrality_threshold) || 0);
    const comparison = planner.ui_insights?.comparison || {};
    const assessment = comparison.assessment || (benefit > threshold ? "better" : benefit < -threshold ? "worse" : "neutral");
    const comparisonText = comparison.comparison_details || (assessment === "better"
      ? `Lepszy od planu bazowego o ${this.formatSignedMoney(benefit)}.`
      : assessment === "worse"
        ? `Plan daje wynik ${this.formatSignedMoney(planner.optimized_result)}, ale jest o ${this.aiFormatNumber(Math.abs(benefit), 2)} zł gorszy od planu bazowego. Został utworzony z uwzględnieniem profili użytkownika.`
        : "Wynik praktycznie taki sam jak plan bazowy.");
    const api = this.aiApiPresentation(planner);
    const purchase = this.aiPurchaseInsights(planner);
    const warnings = [
      planner.plan_status === "blocked" ? "Brak danych SOC — plan został bezpiecznie zablokowany." : "",
      purchase.osd_complete ? "" : "Brak pełnych danych OSD — ranking zakupu jest orientacyjny.",
      api.external ? "" : `${api.status}. ${api.message}`,
    ].filter(Boolean);
    return `<div class="ai-overview-grid">
      <section class="ai-metric-card ai-best-decision"><h3>Przykładowa proponowana zmiana</h3><strong>${representative ? `${this.escapeHtml(representative.label)} · ${this.escapeHtml(this.aiActionLabel(representative.action))}` : "Brak zmiany spełniającej warunki"}</strong><p>${representative ? `Wynik modelowany slotu: ${this.formatSignedMoney(representativeEconomics.slotResult)}. Źródło: ${this.escapeHtml(this.aiSourceLabel(representative))}.` : "Lokalny plan może poprawnie zakończyć się bez zakupu i sprzedaży."}</p>${representative ? "<small>Pełny wynik ekonomiczny modelowanego slotu przy uwzględnieniu przepływów energii i cen. Nie jest to marginalny zysk wywołany samą decyzją; ostatni slot może obejmować wartość terminalną baterii.</small>" : ""}</section>
      <section class="ai-metric-card"><h3>Wynik i porównanie planu</h3><div class="ai-kpis"><div><span>Wynik modelowany całego planu</span><strong>${this.formatSignedMoney(planner.optimized_result)}</strong></div><div><span>Korzyść całego planu względem bazowego</span><strong>${this.formatSignedMoney(benefit)}</strong></div><div><span>Próg neutralności</span><strong>${this.aiFormatNumber(threshold, 2)} zł</strong></div><div><span>Ocena</span><strong>${assessment === "better" ? "lepszy" : assessment === "worse" ? "gorszy" : "neutralny"}</strong></div><div><span>SOC końcowy</span><strong>${this.aiFormatNumber(checkpoints.tomorrow_end, 1)}%</strong></div><div><span>Pewność planu</span><strong>${this.aiFormatNumber(confidence, 0)}%</strong></div></div><small>Pełny wynik ekonomiczny modelowanego planu przy uwzględnieniu przepływów energii i cen. ${this.escapeHtml(comparisonText)}</small></section>
      <section class="ai-metric-card ai-wide-card"><h3>Najlepsze godziny sprzedaży</h3>${this.renderAiSaleRankings(planner)}</section>
      <section class="ai-metric-card ai-wide-card"><h3>Najtańsze godziny zakupu</h3>${this.renderAiPurchaseRanking(planner)}</section>
      <section class="ai-metric-card"><h3>Prognoza SOC 48 h</h3><div class="ai-kpis"><div><span>Koniec dziś</span><strong>${this.aiFormatNumber(checkpoints.today_end, 1)}%</strong></div><div><span>Jutro 05:00</span><strong>${this.aiFormatNumber(checkpoints.tomorrow_05, 1)}%</strong></div><div><span>Jutro 09:00</span><strong>${this.aiFormatNumber(checkpoints.tomorrow_09, 1)}%</strong></div><div><span>Koniec jutro</span><strong>${this.aiFormatNumber(checkpoints.tomorrow_end, 1)}%</strong></div></div><small>Min. SOC użytkownika: ${this.aiFormatNumber(planner.ui_insights?.minimum_soc?.hard_min_soc_pct, 1)}% · efektywne minimum planu: ${this.aiFormatNumber(planner.ui_insights?.minimum_soc?.effective_min_soc_pct, 1)}%</small></section>
      <section class="ai-metric-card"><h3>Wynik modelowany całego planu</h3><p>${dayFinancial("today", "Dziś")}<br>${dayFinancial("tomorrow", "Jutro")}</p><small>Każda wartość dnia jest pełnym wynikiem ekonomicznym modelowanego planu przy uwzględnieniu przepływów energii i cen. To wartość prognozowana, a nie obietnica rezultatu ani wyłącznie przychód z wybranej sprzedaży.</small></section>
      <section class="ai-metric-card ai-wide-card"><h3>Profile użytkownika</h3>${this.renderAiProfileSummaries(planner)}</section>
      <section class="ai-metric-card"><h3>Status planu</h3><ul class="ai-status-list"><li><span>Plan na jutro</span><strong>${this.escapeHtml(this.aiPlanStatus(planner, future))}</strong></li><li><span>Uczenie</span><strong>${this.escapeHtml(this.aiUiText(planner.learning_status || planner.data_quality?.learning_stage || "brak"))}</strong></li><li><span>Asystent API</span><strong>${this.escapeHtml(api.status)}</strong></li><li><span>Przeliczono</span><strong>${this.formatTimeShort(planner.generated_at)}</strong></li><li><span>Powód</span><strong>${this.escapeHtml(this.aiUiText(planner.generation_reason || "brak"))}</strong></li><li><span>Czas</span><strong>${this.aiFormatNumber(planner.duration_ms, 1)} ms</strong></li></ul>${future.status === "scheduled" ? '<button class="ai-cancel-plan" data-cancel-future-plan="1">Anuluj plan na jutro</button>' : ""}</section>
      <section class="ai-metric-card ai-warnings"><h3>Najważniejsze ostrzeżenia</h3>${warnings.length ? `<ul>${warnings.map((item) => `<li>${this.escapeHtml(item)}</li>`).join("")}</ul>` : "<p>Brak aktywnych ostrzeżeń.</p>"}</section>
      ${this.aiCompactWeather()}
    </div>`;
  }

  renderAiProposalView(slots, planner) {
    const day = this._aiDay;
    const allRows = this.aiRowsForDay(planner, day);
    const applicableRows = allRows.filter((row) => this.aiIsApplicableProposal(row));
    const previewCandidates = allRows.filter((row) => this.aiIsPreviewCandidate(row));
    const selectable = allRows.filter((row) => this.aiCanSelectProposal(planner, row, day));
    const visibleRows = allRows.filter((row) => this.aiIsApplicableProposal(row) || this.aiIsPreviewCandidate(row));
    const rows = this._aiShow24 ? allRows : visibleRows;
    const selected = this.aiSelection(day);
    const allSelected = selectable.length > 0 && selectable.every((row) => selected.has(this.aiSlotKey(row.hour)));
    const selectedCount = selectable.filter((row) => selected.has(this.aiSlotKey(row.hour))).length;
    const selectedRows = selectable.filter((row) => selected.has(this.aiSlotKey(row.hour)));
    const selectedEnergy = selectedRows.reduce((sum, row) => sum + (this.asNumber(row.planned_energy_kwh ?? row.energy_kwh) || 0), 0);
    const renderRow = (row) => {
      const key = this.aiSlotKey(row.hour);
      const applicable = this.aiIsApplicableProposal(row);
      const preview = this.aiIsPreviewCandidate(row);
      const canSelect = this.aiCanSelectProposal(planner, row, day);
      const visibleAction = preview ? row.candidate_action : row.action;
      const selling = visibleAction === "sell";
      const charging = visibleAction === "charge";
      const confidenceValue = this.asNumber(row.actual_confidence ?? row.effective_confidence ?? row.confidence);
      const confidence = confidenceValue ?? 0;
      const power = preview ? Math.round(this.asNumber(row.candidate_power_w) || 0) : this.aiPlannedSlotPower(row);
      const energy = this.asNumber(preview ? row.candidate_energy_kwh : row.planned_energy_kwh ?? row.energy_kwh);
      const required = this.asNumber(row.required_confidence);
      const confidenceText = confidenceValue === null
        ? "niedostępna — brak krytycznych danych"
        : preview && required !== null
          ? `Pewność ${this.aiFormatNumber(confidence, 0)}% · wymagane ${this.aiFormatNumber(required, 0)}%`
          : `${this.aiFormatNumber(confidence, 0)}%`;
      const blockReason = row.proposal_block_reason || row.deployment_block_reason;
      const economics = this.aiSlotEconomics(row);
      return `<tr class="${preview ? "preview-candidate" : applicable ? "proposed" : "unchanged"} ${this._aiDetailKey === `${day}-${row.hour}` ? "selected-detail" : ""}" data-ai-hour-detail="${day}-${row.hour}"><td>${canSelect ? `<input type="checkbox" data-ai-plan-row="${key}" ${selected.has(key) ? "checked" : ""}>` : "–"}</td><td>${this.escapeHtml(row.label || this.hourLabel(row.hour))}</td><td>${this.escapeHtml(this.aiActionLabel(visibleAction))}${preview ? `<small>podgląd · ${this.escapeHtml(this.aiUiText(blockReason || "blocked"))}</small>` : ""}</td><td>${this.escapeHtml(this.aiSourceLabel(row))}</td><td>${selling && power > 0 ? `<strong>${power} W</strong><small>${preview ? "kandydat" : "do slotu"}</small>` : charging ? "profil ładowania" : "–"}</td><td>${energy !== null ? `<strong>${this.aiFormatNumber(energy, 2)} kWh</strong><small>${preview ? "kandydat" : "wartość szacowana"}</small>` : "–"}</td><td>${this.aiFormatNumber(row.soc_after, 1)}%</td><td title="Pełny wynik ekonomiczny modelowanego slotu przy uwzględnieniu przepływów energii i cen." class="${(economics.slotResult || 0) >= 0 ? "good" : "warn"}">${this.formatSignedMoney(economics.slotResult)}</td><td><span class="ai-confidence ${this.aiConfidenceClass(confidence)}">${confidenceText}</span></td></tr>`;
    };
    const profileRows = rows.filter((row) => this.aiIsApplicableProposal(row) && !this.aiIsPreviewCandidate(row) && this.aiProfileId(row));
    const optimizerRows = rows.filter((row) => this.aiIsApplicableProposal(row) && !this.aiIsPreviewCandidate(row) && !this.aiProfileId(row));
    const previewRows = rows.filter((row) => this.aiIsPreviewCandidate(row));
    const unchangedRows = rows.filter((row) => !profileRows.includes(row) && !optimizerRows.includes(row) && !previewRows.includes(row));
    const group = (title, groupRows, optional = false) => groupRows.length
      ? `<tr class="ai-plan-group ${optional ? "optional" : ""}"><th colspan="9">${title}</th></tr>${groupRows.map(renderRow).join("")}`
      : "";
    const emptyReason = planner.empty_reason_by_day?.[day] || {};
    const tableRows = rows.length
      ? `${group("A. Realizacja profili użytkownika", profileRows)}${group("B. Sugestie optymalizatora", optimizerRows)}${group("C. Kandydaci — tylko podgląd", previewRows, true)}${group("D. Pozostałe godziny — po zastosowaniu Normalna Praca", unchangedRows, true)}`
      : `<tr><td colspan="9" class="ai-empty">${this.escapeHtml(this.aiUiText(emptyReason.summary || emptyReason.code || "no_proposals"))}</td></tr>`;
    const representative = this.aiRepresentativeProposal(applicableRows) || this.aiRepresentativeProposal(previewCandidates);
    const variants = planner.variants || {};
    const variantSummary = (key, label) => {
      const summary = variants[key]?.days?.find((item) => item.day === day);
      return `<button class="${planner.selected_strategy === key ? "active" : ""}" disabled><strong>${label}</strong><span>${summary ? `SOC ${this.formatNumber(summary.end_soc, 1)}% · ${this.formatNumber(summary.balance_pln, 2)} PLN` : "brak danych"}</span></button>`;
    };
    const quality = planner.data_quality || {};
    const dayRecommendation = planner.recommended_write_by_day?.[day];
    const dayWriteAllowed = dayRecommendation ? dayRecommendation.allowed !== false : planner.recommended_write !== false;
    const detail = allRows.find((row) => `${day}-${row.hour}` === this._aiDetailKey) || representative;
    const detailEconomics = this.aiSlotEconomics(detail);
      const detailCard = detail ? `<section class="ai-hour-detail"><h3>Szczegóły decyzji · ${this.escapeHtml(detail.label || this.hourLabel(detail.hour))}</h3><div class="ai-hour-detail-grid"><div><span>Akcja</span><strong>${this.escapeHtml(this.aiActionLabel(detail.action))}</strong></div><div><span>Źródło decyzji</span><strong>${this.escapeHtml(this.aiSourceLabel(detail))}</strong></div><div><span>Cena</span><strong>${this.aiFormatNumber(detail.action === "sell" ? detail.sell_price : detail.effective_buy_price, 2)} zł/kWh</strong></div><div><span>Czas slotu</span><strong>${Math.max(0, Math.round(this.asNumber(detail.duration_minutes) || 0))} min</strong></div><div><span>Moc przekazywana do slotu</span><strong>${detail.action === "sell" && this.aiIsApplicableProposal(detail) ? `${this.aiPlannedSlotPower(detail)} W` : "nie dotyczy"}</strong></div><div><span>Szacowana energia</span><strong>${this.aiFormatNumber(detail.planned_energy_kwh ?? detail.energy_kwh, 2)} kWh</strong></div><div><span>SOC przed / po</span><strong>${this.aiFormatNumber(detail.soc_start_pct, 1)}% / ${this.aiFormatNumber(detail.soc_end_pct ?? detail.soc_after, 1)}%</strong></div><div><span>PV / dom</span><strong>${this.aiFormatNumber(detail.pv_corrected_kwh ?? detail.corrected_pv_kwh, 2)} / ${this.aiFormatNumber(detail.home_load_kwh ?? detail.load_kwh, 2)} kWh</strong></div><div><span>Cel ładowania</span><strong>${this.escapeHtml(this.aiUiText(detail.purpose || "nie dotyczy"))}</strong></div><div><span>Źródło prognozy PV</span><strong>${detail.pv_forecast_source === "solcast_raw" ? "Surowa prognoza Solcast" : "Lokalna prognoza skorygowana"}</strong></div><div><span>Prognozowana nadwyżka PV</span><strong>${this.aiFormatNumber(detail.predicted_pv_surplus_kwh, 2)} kWh</strong></div><div><span>Możliwy eksport podczas produkcji</span><strong>${this.aiFormatNumber(detail.possible_pv_export_kwh, 2)} kWh</strong></div><div><span>Minimalne wolne miejsce</span><strong>${this.aiFormatNumber(detail.minimum_free_room_kwh, 2)} kWh</strong></div><div><span>Wyliczone wymagane miejsce</span><strong>${this.aiFormatNumber(detail.required_pv_room_kwh, 2)} kWh</strong></div><div><span>Maksymalny SOC przed produkcją</span><strong>${this.aiFormatNumber(detail.max_soc_before_pv_pct, 1)}%</strong></div><div><span>Późniejszy cel</span><strong>${this.escapeHtml(this.aiUiText(detail.future_target_type || "brak"))}${detail.future_target_hour === null || detail.future_target_hour === undefined ? "" : ` · godz. ${String(Number(detail.future_target_hour) % 24).padStart(2, "0")}:00`}</strong></div><div><span>Oczekiwana marża</span><strong>${this.formatSignedMoney(detail.expected_margin)}</strong></div><div><span>Wynik modelowany slotu</span><strong>${this.formatSignedMoney(detailEconomics.slotResult)}</strong></div><div><span>Różnica modelowanych wyników slotu względem bazowego</span><strong>${this.formatSignedMoney(detailEconomics.baselineSlotDelta)}</strong></div><div><span>Pewność</span><strong>${this.aiFormatNumber(detail.confidence, 0)}%</strong></div><div><span>Główne ograniczenie</span><strong>${this.escapeHtml(this.aiUiText(detail.limit_reason || "brak"))}</strong></div></div><p>${(detail.reason_codes || []).map((code) => this.escapeHtml(this.aiUiText(code))).join(" · ") || "Brak dodatkowego uzasadnienia."}</p><p class="ai-note">Pełny wynik ekonomiczny modelowanego slotu uwzględnia przepływy energii i ceny. Różnica względem bazowego porównuje dwa wyniki slotu, lecz nie jest izolowanym counterfactualem samej akcji przy identycznym stanie początkowym. Ostatni slot może obejmować wartość terminalną baterii.</p><p class="ai-note">Do istniejącego harmonogramu zostaną przekazane wyłącznie tryb wybranego slotu i pokazana moc sprzedaży. Energia jest prognozą dla długości slotu; rzeczywisty wynik może być niższy z powodu SOC, zużycia domu lub ograniczeń falownika.</p></section>` : "";
    const api = this.aiApiPresentation(planner);
    return `<div class="ai-proposals-view"><h2>Proponowane zmiany</h2>
      <section class="ai-proposal-explainer"><strong>Co zostanie zapisane?</strong><span>${day === "today" ? "Zaznaczone pozycje będą jedynymi specjalnymi akcjami kompletnego planu na dziś. Wszystkie pozostałe godziny zostaną ustawione jako Normalna Praca — dotyczy to również odznaczonych propozycji oraz starych akcji z wcześniejszego planu." : "Zaznaczone pozycje będą jedynymi specjalnymi akcjami kompletnego, datowanego planu na jutro. Wszystkie pozostałe godziny otrzymają cel Normalna Praca. Akceptacja zapisuje dziś tylko intencję; wykonanie nastąpi jutro JIT, wyłącznie dla aktualnego slotu."}</span><span>Kolumna „Szacowana energia” pokazuje przewidywany rezultat, a nie osobne ustawienie harmonogramu. Pozostałe pola mają charakter informacyjny lub opisują dokładną moc sprzedaży i inne parametry wybranego slotu. Wybrano: <b>${selectedCount} slotów</b> · szacowana energia: <b>${this.aiFormatNumber(selectedEnergy, 2)} kWh</b>.</span></section>
      <div class="ai-proposal-toolbar"><div class="ai-day-tabs"><button class="${day === "today" ? "active" : ""}" data-ai-day="today">Dziś</button><button class="${day === "tomorrow" ? "active" : ""}" data-ai-day="tomorrow">Jutro</button></div><div class="ai-view-tools"><button data-ai-toggle-24="1">${this._aiShow24 ? "Tylko propozycje" : "Pełne 24h"}</button><button class="${allSelected ? "neutral" : "select"}" data-ai-toggle-selection="1" ${!selectable.length ? "disabled" : ""}>${allSelected ? "× Odznacz wszystkie" : "✓ Zaznacz wszystkie"}</button></div></div>
      <div class="ai-plan-table-wrap"><table class="ai-plan-table"><thead><tr><th>Wybór</th><th>Godzina</th><th>Akcja</th><th>Źródło</th><th>Moc do slotu</th><th>Szacowana energia</th><th>SOC po</th><th title="Pełny wynik ekonomiczny modelowanego slotu przy uwzględnieniu przepływów energii i cen.">Wynik modelowany</th><th>Pewność</th></tr></thead><tbody>${tableRows}</tbody></table></div>
      ${detail?.reason_summary ? `<p class="ai-note"><strong>${this.escapeHtml(this.aiUiText(detail.reason_summary))}</strong>${Array.isArray(detail.key_factors) && detail.key_factors.length ? ` · ${detail.key_factors.map((item) => this.escapeHtml(this.aiReadableKeyFactor(item))).join(" · ")}` : ""}</p>` : ""}
      ${detailCard}
      <div class="ai-decision-grid"><section><h3>↗ Przykładowa proponowana zmiana</h3><p>${representative ? `${this.escapeHtml(representative.label)}<br>${this.escapeHtml(this.aiActionLabel(representative.action))} · pewność ${this.aiFormatNumber(representative.confidence, 0)}%` : "Brak decyzji spełniającej warunki"}</p><small>Wiersz jest wybierany chronologicznie do prezentacji, a nie rankingowany przez wynik całego slotu.</small></section><section><h3>⚖ Trzy warianty</h3><div class="ai-variants">${variantSummary("safe", "Bezpieczny")}${variantSummary("balanced", "Zrównoważony")}${variantSummary("profit", "Maksymalny zysk")}</div></section><section><h3>💡 ${api.external ? "Uzasadnienie AI" : "Uzasadnienie planu"}</h3><p>${api.external ? this.escapeHtml(api.summary || "Asystent nie przekazał podsumowania.") : `Plan uwzględnia ceny energii i dystrybucji, Solcast, wyuczony profil domu, sprawność i rezerwę baterii. ${quality.learning_stage === "gotowe" ? "Model ma wystarczającą historię." : "Model jest na etapie wstępnego uczenia, dlatego pewność jest ograniczona."}`}</p><small>Źródło: ${api.external ? `zewnętrzny asystent AI — ${this.escapeHtml(api.provider || "dostawca")} / ${this.escapeHtml(api.model || "model")}${api.candidateValidated ? " · kandydat przeliczony lokalnie" : ""}` : "lokalny Optimizer Core"}. AI nie zapisuje automatycznie ustawień Deye.</small></section></div>
      ${this.aiReadableEnergyChart(allRows, `Plan na ${day === "today" ? "dziś" : "jutro"}`)}
      <div class="ai-support-grid">${this.aiWeatherCard(planner, day)}</div>
      ${dayRecommendation && !dayWriteAllowed ? `<p class="ai-warning">Plan tego dnia nie jest gotowy do zapisu: ${this.escapeHtml(this.aiUiText(dayRecommendation.reason || "no_recommended_changes"))}.</p>` : ""}
      <footer class="ai-action-footer"><button class="ai-apply-plan" data-apply-ai-day="1" ${!selectedCount || !dayWriteAllowed || planner.plan_status === "blocked" ? "disabled" : ""}>${selectedCount ? `${day === "today" ? "Zastosuj wybrane na dziś" : "Zaplanuj wybrane na jutro"} (${selectedCount})` : "Zaznacz przynajmniej jedną godzinę"}</button></footer>
    </div>`;
  }

  renderAiLegacyQualityCard(planner) {
    const quality = planner.data_quality || {};
    const tariff = this.tariffData();
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const learning = aiState?.attributes?.learning_summary || {};
    const weather = aiState?.attributes?.weather || {};
    const mapping = this.state(this.entity("sensor", "mapping_status"), "brak");
    const accuracy = this.asNumber(learning.solcast_accuracy_avg);
    return `<section class="ai-metric-card ai-quality-card"><h3>Dane i jakość</h3><ul><li><span>Status uczenia</span><strong>${quality.learning_stage || "brak"}</strong></li><li><span>Zapisane dni / godziny</span><strong>${quality.recorded_days || 0} / ${learning.recorded_hours || 0}</strong></li><li><span>Trafność zakończonych dni</span><strong>${accuracy === null ? "brak danych" : `${accuracy.toFixed(1)}% (${learning.solcast_accuracy_days || 0} dni)`}</strong></li><li><span>Ceny jutra</span><strong>sprzedaż ${quality.tomorrow_sell_prices || 0}/24 · zakup ${quality.tomorrow_buy_prices || 0}/24</strong></li><li><span>Pogoda / aktualizacja</span><strong>${quality.weather_hours || 0}/48 h · ${this.formatTimeShort(weather.last_updated)}</strong></li><li><span>Profil PV</span><strong>${quality.pv_profile_learned ? "wyuczony" : "krzywa pomocnicza"}</strong></li><li><span>OSD / taryfa</span><strong>${tariff.provider_name || tariff.provider || "brak"} · ${tariff.plan_name || tariff.plan || "brak"}</strong></li><li><span>Wersja katalogu</span><strong>${tariff.catalog_version || "wbudowana"}</strong></li><li><span>Mapowanie Deye</span><strong>${mapping}</strong></li><li><span>Ostatnia analiza</span><strong>${this.formatTimeShort(planner.generated_at)}</strong></li></ul></section>`;
  }

  renderAiQualityCard(planner) {
    const quality = planner.data_quality || {};
    const publication = planner.ui_insights?.price_publication || {};
    const tariff = this.tariffData();
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const learning = aiState?.attributes?.learning_summary || {};
    const maturity = planner.learning_maturity || quality.learning_maturity || learning.learning_maturity || {};
    const readiness = planner.execution_readiness || {};
    const weather = aiState?.attributes?.weather || {};
    const accuracy = this.asNumber(learning.solcast_accuracy_avg);
    const pvDiagnostics = learning.pv_profile_diagnostics || learning.pv_diagnostics || {};
    const loadDiagnostics = learning.load_profile_diagnostics || learning.load_diagnostics || {};
    const channelDiagnostics = learning.channel_diagnostics || quality.channel_diagnostics || {};
    const channelLabels = {
      pv: "Produkcja PV",
      load: "Zużycie domu",
      grid: "Sieć",
      battery: "Bateria",
      soc: "SOC",
      sell_price: "Cena sprzedaży",
      buy_price: "Cena zakupu",
    };
    const channelRows = Object.entries(channelLabels).map(([key, label]) => {
      const item = channelDiagnostics[key] || {};
      const coverage = this.asNumber(item.average_coverage_percent);
      const usable = this.asNumber(item.usable_hours);
      const hours = this.asNumber(item.hours);
      return `<li><span>Kanał · ${label}</span><strong>${coverage === null ? "brak historii jakości" : `${this.aiFormatPercent(coverage, 1)} · użyteczne ${usable ?? 0}/${hours ?? 0} h`}</strong></li>`;
    }).join("");
    const accepted = this.asNumber(quality.pv_profile_samples ?? pvDiagnostics.accepted_samples);
    const rejected = this.asNumber(quality.pv_profile_rejected_samples ?? pvDiagnostics.rejected_samples);
    const sampleTotal = accepted === null && rejected === null ? null : (accepted || 0) + (rejected || 0);
    const completeness = sampleTotal ? (accepted || 0) / sampleTotal * 100 : null;
    const api = this.aiApiPresentation(planner);
    const rows = Array.isArray(planner.rows) ? planner.rows : [];
    const todayRows = rows.filter((row) => row.day === "today");
    const tomorrowRows = rows.filter((row) => row.day === "tomorrow");
    const currentDispatch = todayRows.find((row) => Number(row.hour) === new Date().getHours())?.dispatch_status;
    const executionRows = Array.isArray(planner.profile_execution) ? planner.profile_execution : [];
    const todayDate = todayRows.find((row) => row.date)?.date;
    const todayExecutions = executionRows.filter((row) => !todayDate || row?.date === todayDate);
    const currentExecution = todayExecutions.find((row) => row?.status === "running")
      || todayExecutions.find((row) => row?.status === "waiting")
      || todayExecutions[0];
    const executionLabel = currentExecution
      ? `${this.aiUiText(`profile:${currentExecution.profile_id || ""}`)} · ${this.aiUiText(currentExecution.status || "brak")}`
      : "Brak aktywnej realizacji";
    const average = (values) => {
      const numbers = values.map((value) => this.asNumber(value)).filter((value) => value !== null);
      return numbers.length ? numbers.reduce((sum, value) => sum + value, 0) / numbers.length : null;
    };
    const confidenceLabels = {
      prices: "Ceny energii",
      solcast: "Prognoza Solcast",
      learning: "Stan uczenia",
      load_profile: "Profil zużycia domu",
      pv_profile: "Profil produkcji PV",
      entities: "Dostępność encji",
      soc: "Odczyt SOC",
      tariff_osd: "Taryfa i OSD",
    };
    const confidenceRows = rows.filter((row) => row?.confidence_components);
    const confidenceComponents = Object.fromEntries(
      Object.keys(confidenceLabels).map((key) => [
        key,
        average(confidenceRows.map((row) => row.confidence_components?.[key])),
      ]),
    );
    const todayConfidence = average(todayRows.map((row) => row.confidence));
    const tomorrowConfidence = average(tomorrowRows.map((row) => row.confidence));
    const finalConfidence = average(rows.map((row) => row.confidence));
    const confidenceBreakdown = Object.entries(confidenceLabels)
      .map(([key, label]) => `<li><span>Pewność · ${label}</span><strong>${this.aiFormatPercent(confidenceComponents[key], 0)}</strong></li>`)
      .join("");
    const socDiagnostics = quality.soc || quality.soc_diagnostics || {};
    const requiredCoverage = [
      [quality.today_sell_prices, 24],
      [quality.today_buy_prices, 24],
      [quality.tomorrow_sell_prices, 24],
      [quality.tomorrow_buy_prices, 24],
      [quality.osd_hours, 48],
    ];
    const incompleteInputs = requiredCoverage.some(([value, expected]) => {
      const number = this.asNumber(value);
      return number === null || number < expected;
    });
    const planStatus = quality.fail_closed
      ? "zablokowany — krytyczny brak SOC"
      : incompleteInputs
      ? "obliczony z danymi zastępczymi — pewność ograniczona"
      : "obliczony na kompletnych danych wejściowych";
    return `<section class="ai-metric-card ai-quality-card"><h3>Jakość danych</h3><ul>
      <li><span>Jakość danych</span><strong>${this.aiFormatPercent(quality.score, 0)}</strong></li>
      <li><span>Dojrzałość profilu</span><strong>${this.aiFormatPercent(maturity.score, 0)} · ${this.escapeHtml(maturity.label || this.aiUiText(maturity.status || "brak"))}</strong></li>
      <li><span>Pewność planu</span><strong>${this.aiFormatPercent(planner.plan_confidence ?? finalConfidence, 0)}</strong></li>
      <li><span>Gotowość wykonania</span><strong>${this.escapeHtml(readiness.label || this.aiUiText(readiness.status || "brak"))}</strong></li>
      <li><span>Status uczenia</span><strong>${this.escapeHtml(maturity.label || this.aiUiText(quality.learning_stage || planner.learning_status || "brak"))}</strong></li>
      <li><span>Tryb wdrażania</span><strong>${quality.learning_apply_allowed === false ? "dry-run — plan widoczny, zapis zablokowany" : "wdrażanie dozwolone"}</strong></li>
      <li><span>SOC źródłowy</span><strong>${this.escapeHtml(socDiagnostics.entity_id || "brak encji")} · ${this.escapeHtml(this.aiUiText(socDiagnostics.status || "brak danych"))}</strong></li>
      <li><span>SOC surowy / znormalizowany</span><strong>${this.escapeHtml(String(socDiagnostics.raw_value ?? "brak"))} / ${this.aiFormatPercent(socDiagnostics.normalized_value, 1)}</strong></li>
      <li><span>Źródło świeżości SOC</span><strong>${this.escapeHtml(this.aiUiText(socDiagnostics.source_health_source || socDiagnostics.freshness_reason || "brak"))}</strong></li>
      <li><span>Wiek efektywnej świeżości SOC</span><strong>${this.asNumber(socDiagnostics.effective_soc_age_seconds ?? socDiagnostics.age_seconds) === null ? "brak danych" : `${this.aiFormatNumber(socDiagnostics.effective_soc_age_seconds ?? socDiagnostics.age_seconds, 0)} s`}</strong></li>
      <li><span>Status propozycji</span><strong>${this.escapeHtml(this.aiUiText(planner.plan_status || "brak"))} · ${this.escapeHtml(this.aiUiText(currentDispatch || "brak"))}</strong></li>
      <li><span>Status realizacji profilu</span><strong>${this.escapeHtml(executionLabel)}</strong></li>
      <li><span>Pełne dni nowego profilu</span><strong>${learning.completed_full_days ?? quality.recorded_days ?? "brak danych"}</strong></li>
      <li><span>Historyczne dni dostępne do oceny</span><strong>${learning.solcast_accuracy_days ?? "brak danych"}</strong></li>
      <li><span>Poprawne godziny</span><strong>${learning.recorded_hours ?? "brak danych"}</strong></li>
      <li><span>Godziny użyteczne do nauki</span><strong>${learning.usable_hours ?? quality.usable_history_hours ?? "brak danych"}</strong></li>
      <li><span>Zakres historii</span><strong>${this.escapeHtml(learning.history_first_hour || quality.history_first_hour || "brak")} → ${this.escapeHtml(learning.history_last_hour || quality.history_last_hour || "brak")}</strong></li>
      <li><span>Wszystkie próbki</span><strong>${learning.raw_samples ?? "brak danych"}</strong></li>
      ${channelRows}
      <li><span>Trafność zakończonych dni</span><strong>${this.asNumber(learning.solcast_accuracy_days) === null ? "brak danych" : Number(learning.solcast_accuracy_days) < 1 ? "Brak zakończonych dni" : accuracy === null ? "brak danych" : `${this.aiFormatPercent(accuracy, 1)} — ${learning.solcast_accuracy_days} dni`}</strong></li>
      <li><span>Próbki PV zaakceptowane</span><strong>${accepted === null ? "brak danych" : `${accepted} / ${sampleTotal}`}</strong></li>
      <li><span>Próbki PV odrzucone</span><strong>${rejected === null ? "brak danych" : rejected}</strong></li>
      <li><span>Godziny z curtailmentem</span><strong>${pvDiagnostics.curtailment_hours ?? "brak danych"}</strong></li>
      <li><span>Pokrycie profilu domu</span><strong>${this.aiQualityCoverage(quality.load_profile_covered_cells ?? loadDiagnostics.coverage_cells ?? learning.coverage?.load_cells, 168, "godzin")}</strong></li>
      <li><span>Próbki profilu domu</span><strong>${quality.load_profile_samples ?? "brak danych"}</strong></li>
      <li><span>Próbki profilu PV</span><strong>${quality.pv_profile_samples ?? accepted ?? "brak danych"}</strong></li>
      <li><span>Pokrycie profilu PV</span><strong>${this.aiQualityCoverage(quality.pv_profile_covered_cells, 288, "komórek")}</strong></li>
      <li><span>Fallback profilu domu</span><strong>${this.asNumber(loadDiagnostics.coverage_cells ?? quality.load_profile_covered_cells) === null ? "brak danych" : Number(loadDiagnostics.coverage_cells ?? quality.load_profile_covered_cells) > 0 ? `${loadDiagnostics.fallback_count ?? "brak danych"} godzin` : "brak wystarczających danych"}</strong></li>
      <li><span>Kompletność próbek PV</span><strong>${completeness === null ? "brak wystarczających danych" : this.aiFormatPercent(completeness, 1)}</strong></li>
      <li><span>Plan</span><strong>${planStatus}</strong></li>
      <li><span>Pokrycie cen dzisiaj</span><strong>sprzedaż ${this.aiQualityCoverage(quality.today_sell_prices, 24)} · zakup ${this.aiQualityCoverage(quality.today_buy_prices, 24)}</strong></li>
      <li><span>Pokrycie cen jutro</span><strong>sprzedaż ${this.aiQualityCoverage(quality.tomorrow_sell_prices, 24)} · zakup ${this.aiQualityCoverage(quality.tomorrow_buy_prices, 24)}</strong></li>
      <li><span>Status publikacji cen jutra</span><strong>${this.escapeHtml(this.aiUiText(publication.tomorrow_status || "brak danych"))}</strong></li>
      <li><span>Pokrycie OSD</span><strong>${this.aiQualityCoverage(quality.osd_hours, 48, "godzin")}</strong></li>
      <li><span>Źródło pogody</span><strong>${this.escapeHtml(weather.entity_id || "brak encji")}</strong></li>
      <li><span>Pokrycie pogody</span><strong>${this.aiQualityCoverage(weather.hourly_count, 48, "godzin")} · ${this.aiQualityCoverage(weather.daily_count, 7, "dni")}</strong></li>
      <li><span>Ostatnia aktualizacja pogody</span><strong>${this.formatTimeShort(weather.last_updated)} · ${weather.available ? "dane dostępne" : "brak pełnych danych"}</strong></li>
      <li><span>OSD / taryfa</span><strong>${this.escapeHtml(tariff.provider_name || tariff.provider || "brak")} · ${this.escapeHtml(tariff.plan_name || tariff.plan || "brak")}</strong></li>
      <li><span>Dystrybucja</span><strong>${tariff.price_includes_distribution ? "zawarta w cenie źródłowej" : "doliczana z profilu OSD"}</strong></li>
      <li><span>Asystent AI</span><strong>${this.escapeHtml(api.status)}${api.message ? ` · ${this.escapeHtml(api.message)}` : ""}</strong></li>
      ${confidenceBreakdown}
      <li><span>Pewność planu dzisiaj</span><strong>${this.aiFormatPercent(todayConfidence, 0)}</strong></li>
      <li><span>Pewność planu jutro</span><strong>${this.aiFormatPercent(tomorrowConfidence, 0)}</strong></li>
      <li><span>Pewność końcowa planu</span><strong>${this.aiFormatPercent(finalConfidence, 0)}</strong></li>
      <li><span>Ostatnia analiza</span><strong>${this.formatTimeShort(planner.generated_at)} · ${this.escapeHtml(this.aiUiText(planner.generation_reason || "brak"))} · ${this.aiFormatNumber(planner.duration_ms, 1)} ms</strong></li>
    </ul></section>`;
  }

  renderAiPlanDay(planner, day) {
    const rows = this.aiRowsForDay(planner, day);
    const summary = (planner.days || []).find((item) => item.day === day) || {};
    return `<div class="ai-day-plan"><div class="ai-kpis"><div><span>SOC start</span><strong>${this.formatNumber(summary.start_soc, 1)}%</strong></div><div><span>SOC koniec</span><strong>${this.formatNumber(summary.end_soc, 1)}%</strong></div><div><span>Eksport</span><strong>${this.formatEnergy(summary.sold_kwh || 0)}</strong></div><div><span>Import</span><strong>${this.formatEnergy(summary.bought_kwh || 0)}</strong></div><div title="Pełny wynik ekonomiczny modelowanego planu dnia przy uwzględnieniu przepływów energii i cen."><span>Wynik modelowany dnia</span><strong>${this.formatSignedMoney(summary.balance_pln)}</strong></div></div>${this.aiReadableEnergyChart(rows, day === "today" ? "Plan na dziś" : "Plan na jutro")}${this.aiWeatherCard(planner, day)}</div>`;
  }

  aiExecutionFallback(planner, day) {
    const rows = this.aiRowsForDay(planner, day).map((row) => ({
      date: row.date,
      hour: Number(row.hour),
      label: row.label || this.hourLabel(row.hour),
      proposal_status: row.dispatch_status === "blocked" ? "blocked" : row.proposed ? "proposed" : "skipped",
      approval_status: "not_selected",
      deployment_status: "not_deployed",
      actual_status: "waiting",
      action: row.action || "none",
      profile_id: row.profile_id || "",
      planned_power_w: row.planned_power_w,
      planned_energy_kwh: row.planned_energy_kwh,
      soc_start_pct: row.soc_start_pct,
      soc_end_pct: row.soc_end_pct ?? row.soc_after,
      corrected_pv_kwh: row.corrected_pv_kwh,
      solcast_kwh: row.solcast_kwh,
      load_kwh: row.load_kwh,
      expected_import_kwh: row.expected_import_kwh,
      expected_export_kwh: row.expected_export_kwh,
      sell_price: row.sell_price,
      effective_buy_price: row.effective_buy_price,
      net_result_pln: row.net_result ?? row.balance_pln,
      confidence: row.confidence,
      reason_codes: row.reason_codes || [],
    }));
    const future = this._hass?.states?.[this.entity("sensor", "ai_state")]?.attributes?.future_plan || {};
    if (future.date && rows[0]?.date === future.date) {
      const selected = new Set((future.updates || []).map((item) => String(item.slot_key || "")));
      const results = future.slot_results || {};
      rows.forEach((row) => {
        const key = `${String(row.hour).padStart(2, "0")}_${String((row.hour + 1) % 24).padStart(2, "0")}`;
        if (selected.has(key)) row.approval_status = future.status === "cancelled" ? "cancelled" : "approved";
        if (results[key]?.status === "confirmed") row.deployment_status = "confirmed";
        if (["logical_applied", "physical_pending"].includes(results[key]?.status)) {
          row.deployment_status = results[key].status;
        }
        if (results[key]?.status === "waiting_data") {
          row.deployment_status = "waiting_data";
          row.deployment_reason = results[key]?.reason;
        }
        if (results[key]?.status === "missed") {
          row.deployment_status = "missed";
          row.deployment_reason = results[key]?.reason;
        }
        if (results[key]?.status === "blocked") {
          row.deployment_status = "blocked";
          row.deployment_reason = results[key]?.reason;
        }
        if (results[key]?.status === "manual_override") {
          row.deployment_status = "manual_override";
          row.deployment_reason = results[key]?.reason;
        }
      });
    }
    return { date: rows[0]?.date || "", rows, summary: {} };
  }

  aiExecutionStatus(row) {
    if (row.deployment_status === "confirmed") return ["Potwierdzone fizycznie", "done"];
    if (row.actual_status === "completed") return ["Telemetria kompletna", "done"];
    if (row.actual_status === "partial") return ["Dane częściowe", "partial"];
    if (row.deployment_status === "waiting_data") return ["Oczekuje na dane", "waiting"];
    if (row.deployment_status === "missed") return ["Pominięto", "missed"];
    if (row.deployment_status === "blocked") return ["Zablokowano", "blocked"];
    if (row.deployment_status === "physical_pending") return ["Oczekuje na falownik", "waiting"];
    if (row.deployment_status === "logical_applied") return ["Zapisano logicznie", "waiting"];
    if (row.deployment_status === "manual_override") return ["Zastąpione ręcznie", "blocked"];
    if (row.deployment_status === "deployed") return ["Wdrożono", "deployed"];
    if (row.approval_status === "cancelled") return ["Anulowano", "cancelled"];
    if (row.approval_status === "approved") return ["Zatwierdzono", "approved"];
    if (row.proposal_status === "blocked") {
      const reason = row.deployment_reason || row.reason_summary || row.limit_reason || "brak aktualnych danych krytycznych";
      return [`Core zablokował — ${this.aiUiText(reason)}`, "blocked"];
    }
    if (row.proposal_status === "proposed") return ["Propozycja Core", "proposed"];
    if (row.proposal_status === "missing") return ["Brak zapisanego planu", "missing"];
    return ["Bez zmiany", "skipped"];
  }

  aiExecutionNumber(value, digits = 2, unit = "") {
    const number = this.asNumber(value);
    return number === null ? "—" : `${number.toFixed(digits).replace(".", ",")}${unit}`;
  }

  renderAiExecutionChart(data, title, showNowLine = false) {
    const rows = Array.isArray(data?.rows) ? data.rows : [];
    if (!rows.length) return `<section class="ai-chart-card ai-execution-chart"><h3>${this.escapeHtml(title)}</h3><div class="ai-empty-state"><span class="ai-empty-icon">📉</span><strong>Brak zamrożonych danych dla wybranego dnia.</strong></div></section>`;
    const width = 1200;
    const height = 430;
    const left = 58;
    const right = 70;
    const top = 38;
    const plotHeight = 310;
    const bottom = top + plotHeight;
    const zeroY = top + plotHeight / 2;
    const statusTop = bottom + 12;
    const statusHeight = 18;
    const step = (width - left - right) / 24;
    const byHour = new Map(rows.map((row) => [Number(row.hour), row]));
    const values = Array.from({ length: 24 }, (_, hour) => byHour.get(hour) || { hour });
    const energyValues = values.flatMap((row) => [
      row.corrected_pv_kwh, row.load_kwh, row.expected_export_kwh,
      row.actual?.pv_kwh, row.actual?.load_kwh, row.actual?.grid_export_kwh,
      row.expected_import_kwh, row.actual?.grid_import_kwh,
    ]).map((value) => this.asNumber(value)).filter((value) => value !== null);
    const maxEnergy = Math.max(1, ...energyValues);
    const x = (index) => left + step * (index + .5);
    const yEnergy = (value) => zeroY - Math.max(0, Number(value || 0)) / maxEnergy * (plotHeight / 2);
    const ySoc = (value) => bottom - Math.max(0, Math.min(100, Number(value || 0))) / 100 * plotHeight;
    const formatMoney = (value) => this.aiExecutionNumber(value, 2, " zł");
    const formatEnergy = (value) => this.aiExecutionNumber(value, 2, " kWh");
    const formatSoc = (value) => this.aiExecutionNumber(value, 1, " %");
    const tickLabel = (value) => {
      if (Math.abs(value) < 0.05) return "0";
      const text = Math.abs(value) >= 10 ? String(Math.round(value)) : value.toFixed(1);
      return text.replace(".", ",");
    };
    const gridParts = [0, .25, .5, .75, 1];
    const grid = gridParts.map((part) => {
      const y = top + plotHeight * part;
      return `<line x1="${left}" y1="${y}" x2="${width - right}" y2="${y}" class="ai-exec-grid"/>` +
        `<text x="${left - 9}" y="${y + 4}" text-anchor="end" class="ai-readable-axis">${tickLabel(maxEnergy * (1 - 2 * part))}</text>` +
        `<text x="${width - right + 7}" y="${y + 4}" class="ai-readable-axis">${(100 * (1 - part)).toFixed(0)}%</text>`;
    }).join("");
    const bar = (value, index, offset, css, down = false) => {
      const number = this.asNumber(value);
      if (number === null || number === 0) return "";
      const barWidth = Math.max(3, step * .10);
      const xv = x(index) + step * offset;
      if (down) {
        const h = Math.max(0, number / maxEnergy * (plotHeight / 2));
        return `<rect x="${xv - barWidth / 2}" y="${zeroY}" width="${barWidth}" height="${h}" rx="2" class="${css}"/>`;
      }
      const y = yEnergy(number);
      return `<rect x="${xv - barWidth / 2}" y="${y}" width="${barWidth}" height="${Math.max(0, zeroY - y)}" rx="2" class="${css}"/>`;
    };
    const bars = values.map((row, index) => [
      bar(row.corrected_pv_kwh, index, -.165, "ai-exec-pv-plan"),
      bar(row.actual?.pv_kwh, index, -.055, "ai-exec-pv-wykonanie"),
      bar(row.load_kwh, index, .055, "ai-exec-load-plan"),
      bar(row.actual?.load_kwh, index, .165, "ai-exec-load-wykonanie"),
      bar(row.expected_export_kwh, index, .275, "ai-exec-export-plan"),
      bar(row.actual?.grid_export_kwh, index, .385, "ai-exec-export-wykonanie"),
      bar(row.expected_import_kwh, index, -.275, "ai-exec-import-plan", true),
      bar(row.actual?.grid_import_kwh, index, -.385, "ai-exec-import-wykonanie", true),
    ].join("")).join("");
    const line = (getter, css) => {
      const points = values.map((row, index) => {
        const value = this.asNumber(getter(row));
        return value === null ? null : `${x(index)},${ySoc(value)}`;
      }).filter(Boolean);
      return points.length > 1 ? `<polyline points="${points.join(" ")}" class="${css}"/>` : "";
    };
    const statuses = values.map((row, index) => {
      const [, statusClass] = this.aiExecutionStatus(row);
      return `<rect x="${left + index * step + 1}" y="${statusTop}" width="${Math.max(2, step - 2)}" height="${statusHeight}" rx="4" class="ai-exec-status ${statusClass}"/>`;
    }).join("");
    const vGrid = values.map((row, index) => (index % 3 === 0 || index === 23)
      ? `<line x1="${x(index)}" y1="${top}" x2="${x(index)}" y2="${bottom}" class="ai-exec-grid-v"/>`
      : "").join("");
    const hours = values.map((row, index) => (index % 3 === 0 || index === 23)
      ? `<text x="${x(index)}" y="${bottom + 42}" text-anchor="middle" class="ai-readable-hour">${String(index).padStart(2, "0")}:00</text>`
      : "").join("");
    const nowLine = showNowLine ? this.renderAiExecutionNowLine(left, right, bottom, top, width) : "";
    const hitBoxes = values.map((row, index) => `<rect x="${left + index * step}" y="${top}" width="${step}" height="${plotHeight + statusHeight + 28}" fill="transparent" class="ai-chart-hit" data-ai-chart-point="execution" data-ai-chart-index="${index}"/>`).join("");
    const tooltipData = values.map((row, index) => {
      const [status, statusClass] = this.aiExecutionStatus(row);
      const actual = row.actual || {};
      const action = row.action === "sell" ? "Sprzedaż" : row.action === "charge" ? "Ładowanie" : "Bez zmiany";
      return { index, status, statusClass, action, row, actual };
    });
    const tipSources = tooltipData.map((item) => this._renderAiExecutionTip(item, formatMoney, formatEnergy, formatSoc)).join("");
    const legend = [
      ["pv-plan", "PV plan"], ["pv-wykonanie", "PV wykonanie"], ["load-plan", "Dom plan"],
      ["load-wykonanie", "Dom wykonanie"], ["soc-plan", "SOC plan"], ["soc-wykonanie", "SOC wykonanie"],
    ].map(([css, label]) => `<span class="${css}"><i></i>${label}</span>`).join("");
    return `<section class="ai-chart-card ai-execution-chart" data-ai-chart="execution"><h3>${this.escapeHtml(title)}</h3><div class="ai-execution-legend">${legend}</div><div class="ai-chart-scroll"><svg viewBox="0 0 ${width} ${height}" style="min-width:${width}px" role="img" aria-label="${this.escapeHtml(title)}"><defs>${this._aiExecutionGradients()}</defs><text x="10" y="22" class="ai-readable-unit">kWh</text><text x="${width - 10}" y="22" text-anchor="end" class="ai-readable-unit">SOC %</text>${grid}${vGrid}${bars}${line((row) => row.soc_end_pct, "ai-exec-soc-plan")}${line((row) => row.actual?.soc_end_pct, "ai-exec-soc-wykonanie")}${nowLine}<line x1="${left}" y1="${zeroY}" x2="${width - right}" y2="${zeroY}" class="ai-exec-baseline"/>${hours}<text x="10" y="${statusTop + 13}" class="ai-readable-section-label">Status</text>${statuses}${hitBoxes}<line class="ai-chart-crosshair-x" x1="0" y1="${top}" x2="0" y2="${bottom}"/><line class="ai-chart-crosshair-y" x1="${left}" y1="0" x2="${width - right}" y2="0"/></svg></div><div class="ai-execution-status-legend"><span class="proposed">Propozycja Core</span><span class="approved">Zatwierdzono</span><span class="deployed">Wdrożono</span><span class="done">Wykonano</span><span class="blocked">Zablokowano</span></div><div class="ai-chart-tooltip" data-ai-chart-tooltip></div>${tipSources}</section>`;
  }

  _aiExecutionGradients() {
    return `<linearGradient id="aiExecGradPvPlan" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#9ccc65" stop-opacity=".95"/><stop offset="100%" stop-color="#7cb342" stop-opacity=".75"/></linearGradient>` +
      `<linearGradient id="aiExecGradPvWyk" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#69f0ae" stop-opacity=".95"/><stop offset="100%" stop-color="#00e676" stop-opacity=".75"/></linearGradient>` +
      `<linearGradient id="aiExecGradLoadPlan" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ffca28" stop-opacity=".95"/><stop offset="100%" stop-color="#ff9f43" stop-opacity=".75"/></linearGradient>` +
      `<linearGradient id="aiExecGradLoadWyk" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#64b5f6" stop-opacity=".95"/><stop offset="100%" stop-color="#42a5f5" stop-opacity=".75"/></linearGradient>` +
      `<linearGradient id="aiExecGradExportPlan" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#00e5ff" stop-opacity=".95"/><stop offset="100%" stop-color="#00b8d4" stop-opacity=".75"/></linearGradient>` +
      `<linearGradient id="aiExecGradExportWyk" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#80f7ff" stop-opacity=".95"/><stop offset="100%" stop-color="#00e5ff" stop-opacity=".75"/></linearGradient>` +
      `<linearGradient id="aiExecGradImportPlan" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ff8a80" stop-opacity=".95"/><stop offset="100%" stop-color="#ff5252" stop-opacity=".75"/></linearGradient>` +
      `<linearGradient id="aiExecGradImportWyk" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ff5252" stop-opacity=".95"/><stop offset="100%" stop-color="#d50000" stop-opacity=".75"/></linearGradient>`;
  }

  _renderAiExecutionTip(item, formatMoney, formatEnergy, formatSoc) {
    if (!item) return "";
    const { index, row, actual, status, statusClass, action } = item;
    const hasActual = [actual.pv_kwh, actual.load_kwh, actual.soc_end_pct, actual.grid_import_kwh, actual.grid_export_kwh, actual.net_result_pln]
      .some((value) => this.asNumber(value) !== null);
    const profile = row.profile_id ? this.aiUiText(`profile:${row.profile_id}`) : this.aiUiText(row.decision_source || "optimizer");
    const pairRow = (label, planText, actualText) => hasActual
      ? `<span>${label} plan / wyk.</span><b>${planText} / ${actualText}</b>`
      : `<span>${label} plan</span><b>${planText}</b>`;
    return `<div class="ai-chart-tip-source" data-ai-tip-source="execution-${index}"><strong>${this.escapeHtml(row.label || this.hourLabel(row.hour))} · <span class="${statusClass}">${status}</span></strong><div><span>Akcja</span><b>${action}</b><span>Profil</span><b>${this.escapeHtml(profile)}</b><span>Moc slotu</span><b>${this.aiExecutionNumber(row.planned_power_w, 0, " W")}</b></div><div class="ai-exec-tip-sep"></div><div>${pairRow("PV", formatEnergy(row.corrected_pv_kwh), formatEnergy(actual.pv_kwh))}${pairRow("Dom", formatEnergy(row.load_kwh), formatEnergy(actual.load_kwh))}${pairRow("SOC", formatSoc(row.soc_end_pct), formatSoc(actual.soc_end_pct))}${pairRow("Import", formatEnergy(row.expected_import_kwh), formatEnergy(actual.grid_import_kwh))}${pairRow("Eksport", formatEnergy(row.expected_export_kwh), formatEnergy(actual.grid_export_kwh))}</div><div class="ai-exec-tip-sep"></div><div><span>Cena kupna</span><b>${this.aiExecutionNumber(row.effective_buy_price, 2, " zł/kWh")}</b><span>Cena sprzedaży</span><b>${this.aiExecutionNumber(row.sell_price, 2, " zł/kWh")}</b>${pairRow("Pełny wynik ekonomiczny", formatMoney(row.net_result_pln), formatMoney(actual.net_result_pln))}</div></div>`;
  }

  renderAiExecutionNowLine(left, right, bottom, top, width = 1400) {
    const now = new Date();
    const minutes = now.getHours() * 60 + now.getMinutes();
    const plotWidth = width - left - right;
    const x = left + (minutes / 1440) * plotWidth;
    if (x < left || x > width - right) return "";
    return `<line x1="${x}" y1="${top}" x2="${x}" y2="${bottom}" class="ai-now-line"/><text x="${x + 4}" y="${top + 14}" class="ai-now-label">teraz</text>`;
  }

  renderAiExecutionTable(data, planOnly = false) {
    const rows = Array.isArray(data?.rows) ? data.rows : [];
    if (!rows.length) return `<div class="ai-empty-state"><span class="ai-empty-icon">📋</span><strong>Brak danych godzinowych dla wybranego dnia.</strong></div>`;
    const numberCell = (value, digits = 2, unit = "", cls = "") => `<td class="${cls}">${this.aiExecutionNumber(value, digits)}${unit ? ` <span class="ai-exec-unit">${unit}</span>` : ""}</td>`;
    const priceCell = (sell, buy, cls = "") => `<td class="${cls}"><span class="ai-exec-price-sell">${this.aiExecutionNumber(sell, 2)}</span><span class="ai-exec-price-sep">/</span><span class="ai-exec-price-buy">${this.aiExecutionNumber(buy, 2)}</span></td>`;
    const sum = (field, actualField) => rows.reduce((acc, row) => acc + (this.asNumber(actualField ? row.actual?.[actualField] : row[field]) || 0), 0);
    const emptyCell = `<td></td>`;
    const wykonanieClass = (plan, wykonanie) => {
      const p = this.asNumber(plan);
      const w = this.asNumber(wykonanie);
      if (p === null || w === null) return "";
      const diff = Math.abs(p - w);
      return diff > p * 0.2 + 0.05 ? " ai-exec-wykonanie-diverge" : diff > p * 0.08 + 0.02 ? " ai-exec-wykonanie-off" : " ai-exec-wykonanie-match";
    };
    const footer = planOnly ? "" : `<tfoot><tr class="ai-exec-summary"><td class="ai-exec-col-hour"><strong>SUMA</strong></td><td class="ai-exec-col-status"></td><td class="ai-exec-col-action"></td><td class="ai-exec-col-power"></td>${emptyCell}${emptyCell}${numberCell(sum("corrected_pv_kwh"), 2, "")}${numberCell(sum("actual", "pv_kwh"), 2, "")}${numberCell(sum("load_kwh"), 2, "")}${numberCell(sum("actual", "load_kwh"), 2, "")}${numberCell(sum("expected_import_kwh"), 2, "")}${numberCell(sum("actual", "grid_import_kwh"), 2, "")}${numberCell(sum("expected_export_kwh"), 2, "")}${numberCell(sum("actual", "grid_export_kwh"), 2, "")}${emptyCell}${numberCell(sum("net_result_pln"), 2, "")}${numberCell(sum("actual", "net_result_pln"), 2, "")}${emptyCell}${emptyCell}</tr></tfoot>`;
    const body = rows.map((row, idx) => {
      const [status, statusClass] = this.aiExecutionStatus(row);
      const actual = row.actual || {};
      const errors = row.errors || {};
      const action = row.action === "sell" ? "Sprzedaż" : row.action === "charge" ? "Ładowanie" : "Bez zmiany";
      const source = row.profile_id ? this.aiUiText(`profile:${row.profile_id}`) : this.aiUiText(row.decision_source || "optimizer");
      const pvPlan = this.aiExecutionNumber(row.corrected_pv_kwh, 2);
      const pvWyk = this.aiExecutionNumber(actual.pv_kwh, 2);
      const domPlan = this.aiExecutionNumber(row.load_kwh, 2);
      const domWyk = this.aiExecutionNumber(actual.load_kwh, 2);
      const impPlan = this.aiExecutionNumber(row.expected_import_kwh, 2);
      const impWyk = this.aiExecutionNumber(actual.grid_import_kwh, 2);
      const expPlan = this.aiExecutionNumber(row.expected_export_kwh, 2);
      const expWyk = this.aiExecutionNumber(actual.grid_export_kwh, 2);
      const pricePlan = `<span class="ai-exec-price-buy">${this.aiExecutionNumber(row.effective_buy_price, 2)}</span><span class="ai-exec-price-sep">/</span><span class="ai-exec-price-sell">${this.aiExecutionNumber(row.sell_price, 2)}</span>`;
      return `<tr class="${idx % 2 === 0 ? "" : "ai-exec-odd"}"><td class="ai-exec-col-hour"><strong>${this.escapeHtml(row.label || this.hourLabel(row.hour))}</strong></td><td class="ai-exec-col-status"><span class="ai-exec-badge ${statusClass}" title="${this.escapeHtml(this.aiUiText(row.deployment_reason || ""))}">${status}</span></td><td class="ai-exec-col-action"><span class="ai-exec-action">${action}</span><span class="ai-exec-source">${this.escapeHtml(source)}</span></td><td class="ai-exec-col-power">${this.aiExecutionNumber(row.planned_power_w, 0, " W")}</td>${numberCell(row.soc_end_pct, 1, "%")}${numberCell(actual.soc_end_pct, 1, "%", "ai-exec-wykonanie" + wykonanieClass(row.soc_end_pct, actual.soc_end_pct))}<td>${pvPlan}</td><td class="ai-exec-wykonanie${wykonanieClass(row.corrected_pv_kwh, actual.pv_kwh)}">${pvWyk}</td><td>${domPlan}</td><td class="ai-exec-wykonanie${wykonanieClass(row.load_kwh, actual.load_kwh)}">${domWyk}</td><td>${impPlan}</td><td class="ai-exec-wykonanie${wykonanieClass(row.expected_import_kwh, actual.grid_import_kwh)}">${impWyk}</td><td>${expPlan}</td><td class="ai-exec-wykonanie${wykonanieClass(row.expected_export_kwh, actual.grid_export_kwh)}">${expWyk}</td><td>${pricePlan}</td><td>${this.aiExecutionNumber(row.net_result_pln, 2)}</td><td class="ai-exec-wykonanie${wykonanieClass(row.net_result_pln, actual.net_result_pln)}">${this.aiExecutionNumber(actual.net_result_pln, 2)}</td><td colspan="2" class="ai-exec-col-error">${this.aiExecutionNumber(errors.pv_percent, 1, "%")}<span class="ai-exec-error-sep">/</span>${this.aiExecutionNumber(errors.load_percent, 1, "%")}</td></tr>`;
    }).join("");
    return `<div class="ai-plan-table-wrap ai-execution-table-wrap"><table class="ai-plan-table ai-execution-table"><thead><tr class="ai-exec-head-main"><th rowspan="2" class="ai-exec-col-hour">Godzina</th><th rowspan="2" class="ai-exec-col-status">Status</th><th rowspan="2" class="ai-exec-col-action">Akcja / profil</th><th rowspan="2" class="ai-exec-col-power">Moc</th><th colspan="2">SOC (%)</th><th colspan="2" class="ai-exec-group-pv">PV (kWh)</th><th colspan="2" class="ai-exec-group-dom">Dom (kWh)</th><th colspan="2" class="ai-exec-group-imp">Import (kWh)</th><th colspan="2" class="ai-exec-group-exp">Eksport (kWh)</th><th>Cena (zł/kWh)</th><th colspan="2" title="Pełny wynik ekonomiczny slotu przy uwzględnieniu przepływów energii i cen.">Wynik ekonomiczny (zł)</th><th colspan="2" class="ai-exec-col-error">Błąd prognozy (%)</th></tr><tr class="ai-exec-head-sub"><th>Plan</th><th>Wykonanie</th><th>Plan</th><th>Wykonanie</th><th>Plan</th><th>Wykonanie</th><th>Plan</th><th>Wykonanie</th><th>Plan</th><th>Wykonanie</th><th>Plan: kupno / sprzedaż</th><th>Plan</th><th>Wykonanie</th><th>PV</th><th>Dom</th></tr></thead><tbody>${body}</tbody>${footer}</table></div>`;
  }
  renderAiPlanExecution(planner) {
    const aiState = this._hass?.states?.[this.entity("sensor", "ai_state")];
    const attrs = aiState?.attributes || {};
    const range = this._aiExecutionRange || "today";
    const buttons = [["today", "Dziś"], ["tomorrow", "Jutro"], ["48h", "48 h"], ["history", "Historia"]]
      .map(([key, label]) => `<button type="button" class="${range === key ? "active" : ""}" data-ai-execution-range="${key}">${label}</button>`).join("");
    if (range === "48h") {
      return `<div class="ai-plan-execution"><div class="ai-execution-toolbar"><div class="ai-day-tabs">${buttons}</div></div>${this.aiReadableEnergyChart(planner.rows || [], "Plan energii 48 h")}<div class="ai-execution-note">Widok 48 h przedstawia aktualną propozycję Core. Dane historyczne są zamrażane osobno dla każdej godziny i nie są przeliczane wstecz.</div></div>`;
    }
    if (range === "history") {
      const index = attrs.plan_execution_index || {};
      const available = Array.isArray(index.available_dates) ? index.available_dates : [];
      const selectedDate = this._aiExecutionDate || available[0] || this.localDateKey(new Date());
      const data = this._aiExecutionData?.date === selectedDate ? this._aiExecutionData : null;
      const content = this._aiExecutionLoading
        ? `<div class="ai-empty-state"><span class="ai-empty-icon">⏳</span><strong>Pobieranie zamrożonego planu i pomiarów…</strong></div>`
        : this._aiExecutionError
        ? `<div class="ai-empty-state ai-empty-error"><span class="ai-empty-icon">⚠</span><strong>${this.escapeHtml(this._aiExecutionError)}</strong></div>`
        : data
        ? `${this.renderAiExecutionChart(data, `Plan i wykonanie · ${selectedDate}`, selectedDate === this.localDateKey(new Date()))}${this.renderAiExecutionTable(data)}`
        : `<div class="ai-empty-state"><span class="ai-empty-icon">🗂️</span><strong>Brak wybranego dnia historii</strong><span>Wybierz datę i użyj „Pokaż dzień”.</span><small>Dostępne dni: ${available.length}</small></div>`;
      return `<div class="ai-plan-execution"><div class="ai-execution-toolbar"><div class="ai-day-tabs">${buttons}</div><div class="ai-execution-date"><input type="date" value="${this.escapeHtml(selectedDate)}" min="${this.escapeHtml(available[available.length - 1] || "")}" max="${this.escapeHtml(available[0] || this.localDateKey(new Date()))}" data-ai-execution-date><button type="button" data-ai-execution-load>Pokaż dzień</button></div></div>${content}</div>`;
    }
    const day = range === "tomorrow" ? "tomorrow" : "today";
    const data = day === "today" && attrs.plan_execution_today?.rows?.length
      ? attrs.plan_execution_today
      : this.aiExecutionFallback(planner, day);
    const summary = data.summary || {};
    const isPlanOnly = day === "tomorrow";
    const title = isPlanOnly ? "Jutro · plan" : "Dziś · plan i wykonanie";
    const sumRows = (field, actualField) => (data.rows || []).reduce((acc, row) => acc + (this.asNumber(actualField ? row.actual?.[actualField] : row[field]) || 0), 0);
    const planned_import_kwh = summary.planned_import_kwh ?? sumRows("expected_import_kwh");
    const actual_import_kwh = summary.actual_import_kwh ?? sumRows("grid_import_kwh", true);
    const kpi = (icon, title, plan, wykonanie, unit, cls = "") => {
      const planText = this.aiExecutionNumber(plan, 2);
      const wykText = this.aiExecutionNumber(wykonanie, 2);
      return `<div class="ai-exec-kpi ${cls}"><div class="ai-exec-kpi-icon">${icon}</div><div class="ai-exec-kpi-body"><span class="ai-exec-kpi-title">${title}</span><div class="ai-exec-kpi-row">${isPlanOnly ? `<div class="ai-exec-kpi-pair"><small>Plan</small><b class="ai-exec-kpi-plan">${planText} <span class="ai-exec-kpi-unit">${unit}</span></b></div>` : `<div class="ai-exec-kpi-pair"><small>Plan</small><b class="ai-exec-kpi-plan">${planText} <span class="ai-exec-kpi-unit">${unit}</span></b></div><div class="ai-exec-kpi-pair"><small>Wykonanie</small><b class="ai-exec-kpi-wykonanie">${wykText} <span class="ai-exec-kpi-unit">${unit}</span></b></div>`}</div></div></div>`;
    };
    const summaryCards = `<div class="ai-execution-kpis">${kpi("☀", "PV", summary.planned_pv_kwh, summary.actual_pv_kwh, "kWh", "ai-exec-kpi-pv")}${kpi("🏠", "Dom", summary.planned_load_kwh, summary.actual_load_kwh, "kWh", "ai-exec-kpi-dom")}${kpi("↗", "Eksport", summary.planned_export_kwh, summary.actual_export_kwh, "kWh", "ai-exec-kpi-exp")}${kpi("↘", "Import", planned_import_kwh, actual_import_kwh, "kWh", "ai-exec-kpi-imp")}${kpi("zł", "Wynik ekonomiczny", summary.planned_result_pln, summary.actual_result_pln, "zł", "ai-exec-kpi-wynik")}</div>`;
    const explainer = `<details class="ai-execution-info"><summary>ℹ Co oznaczają dane?</summary><p>Plan to zamrożona propozycja Optimizer Core. Wykonanie pochodzi z zakończonych pomiarów godzinowych. Wynik ekonomiczny jest pełnym bilansem przepływów energii i cen dla planu lub wykonania, a nie zyskiem samej decyzji. Sam ten widok niczego nie zapisuje do harmonogramu ani Deye.</p></details>`;
    return `<div class="ai-plan-execution"><div class="ai-execution-toolbar"><div class="ai-day-tabs">${buttons}</div>${explainer}</div>${summaryCards}${this.renderAiExecutionChart(data, title, !isPlanOnly)}${this.renderAiExecutionTable(data, isPlanOnly)}</div>`;
  }

  async loadAiExecutionDay(dateKey) {
    if (!dateKey || !this._hass?.callWS) return;
    this._aiExecutionDate = dateKey;
    this._aiExecutionLoading = true;
    this._aiExecutionError = "";
    this.renderDialogOnly();
    try {
      const result = await this._hass.callWS({
        type: "call_service",
        domain: "deye_energy_manager",
        service: "get_plan_execution",
        service_data: { date: dateKey },
        return_response: true,
      });
      this._aiExecutionData = result?.response || result || null;
    } catch (error) {
      this._aiExecutionError = `Nie udało się pobrać danych dnia: ${error?.message || error}`;
    } finally {
      this._aiExecutionLoading = false;
      this.renderDialogOnly();
    }
  }

  renderAiDialog(slots) {
    const planner = this.aiPlannerData(slots);
    const nav = [
      ["overview", "⌂", "Przegląd"], ["proposals", "↗", "Proponowane zmiany"],
      ["explanation", "?", "Dlaczego ten plan?"],
      ["execution", "▣", "Plan i wykonanie"], ["quality", "▦", "Jakość danych"],
    ].map(([key, icon, label]) => `<button class="${this._aiView === key ? "active" : ""}" data-ai-view="${key}"><span>${icon}</span>${label}</button>`).join("");
    let body = this.renderAiOverview(slots, planner);
    if (this._aiView === "proposals") body = this.renderAiProposalView(slots, planner);
    if (this._aiView === "explanation") body = this.renderAiExplanation(planner);
    if (this._aiView === "execution") body = this.renderAiPlanExecution(planner);
    if (this._aiView === "quality") body = `<div class="ai-quality-full">${this.renderAiQualityCard(planner)}</div>`;
    const quality = planner.data_quality || {};
    const maturity = planner.learning_maturity || quality.learning_maturity || {};
    return `<div class="overlay" data-close-dialog="1"><section class="dialog ai-dialog ai-dialog-v2" data-dialog-box="1"><div class="dialog-head"><strong>Sugestie AI</strong><button type="button" data-close-dialog="1">${this.iconSvg("close")}</button></div><div class="ai-shell"><aside class="ai-sidebar"><nav>${nav}</nav><div class="ai-learning-status"><span>Dojrzałość profilu</span><strong>${this.escapeHtml(String(maturity.label || this.aiUiText(maturity.status || "brak")).toUpperCase())}</strong><small>${this.aiFormatPercent(maturity.score, 0)} · użyteczne godziny: ${maturity.valid_hours ?? quality.usable_history_hours ?? 0}</small></div></aside><main class="ai-main" data-scroll-key="ai-main">${body}</main></div></section></div>`;
  }

  renderAnalysisDetails(item) {
    const strategy = {
      balanced: "Zrównoważony",
      profit: "Maksymalny zysk",
      autoconsumption: "Maksymalna autokonsumpcja",
    }[item.strategy] || item.strategy || "Brak danych";
    const priceRows = (rows, empty) => Array.isArray(rows) && rows.length
      ? rows.map(([hour, price]) => `<li><strong>${this.hourLabel(hour)}</strong><span>${this.formatPrice(price)} PLN/kWh</span></li>`).join("")
      : `<li><span>${empty}</span></li>`;
    const sellRows = priceRows(item.bestSell, "Brak godzin spełniających warunki sprzedaży");
    const buyRows = priceRows(item.cheapBuy, "Brak godzin spełniających warunki zakupu");
    const applied = item.event === "accepted" || item.accepted
      ? "Zastosowana ręcznie"
      : item.event === "daily_summary" ? "Podsumowanie dnia" : "Nie zastosowano";
    const reason = item.event === "daily_summary"
      ? "Podsumowanie zebranych danych dobowych."
      : item.strategy === "profit"
        ? "Wybrano godziny o najwyższych cenach sprzedaży i najniższych cenach zakupu."
        : item.strategy === "autoconsumption"
          ? "Priorytetem jest wykorzystanie energii w domu i ograniczenie poboru z sieci."
          : "Sugestia równoważy ceny energii, prognozę PV, zużycie domu i rezerwę magazynu.";
    const outcome = item.outcome
      ? `${this.formatNumber(item.outcome.sold_kwh, 2)} kWh / ${this.formatNumber(item.outcome.sold_value, 2)} PLN, trafność PV ${this.formatNumber(item.outcome.pv_accuracy_percent, 0)}%`
      : item.rating ? `Ocena użytkownika: ${item.rating}/5` : "Brak zakończonego wyniku";
    const correction = this.asNumber(item.forecastCorrection);
    const predictedSoc = this.asNumber(item.predictedSoc);
    const maxSellPower = this.asNumber(item.maxSellPower);
    const minSoc = this.asNumber(item.minSoc);
    return `<div class="analysis-details">
      <div class="analysis-detail-grid">
        <div><span>Status</span><strong>${applied}</strong></div>
        <div><span>Strategia</span><strong>${this.escapeHtml(strategy)}</strong></div>
        <div><span>Maks. moc sprzedaży</span><strong>${maxSellPower === null ? "Brak danych" : `${this.formatNumber(maxSellPower, 0)} W`}</strong></div>
        <div><span>Minimalny SOC</span><strong>${minSoc === null ? "Brak danych" : `${this.formatNumber(minSoc, 0)}%`}</strong></div>
        <div><span>Prognoza Solcast</span><strong>${this.formatNumber(item.solcastToday, 2)} kWh</strong></div>
        <div><span>Pozostała prognoza</span><strong>${this.formatNumber(item.solcastRemaining, 2)} kWh</strong></div>
        <div><span>Rzeczywista produkcja PV</span><strong>${this.formatNumber(item.dailyPv, 2)} kWh</strong></div>
        <div><span>Korekta prognozy</span><strong>${correction === null ? "Brak danych" : `${this.formatNumber(correction * 100, 0)}%`}</strong></div>
        <div><span>Przewidywane zużycie domu</span><strong>${this.formatNumber(item.expectedRemainingLoad, 2)} kWh</strong></div>
        <div><span>Szacowana nadwyżka</span><strong>${this.formatNumber(item.estimatedSurplus, 2)} kWh</strong></div>
        <div><span>Prognozowany SOC</span><strong>${predictedSoc === null ? "Brak danych" : `${this.formatNumber(predictedSoc, 0)}%`}</strong></div>
        <div><span>Trend magazynu</span><strong>${this.escapeHtml(item.predictedSocTrend || "Brak danych")}</strong></div>
      </div>
      <div class="analysis-price-groups">
        <section><h4>Najlepsze godziny sprzedaży</h4><ul>${sellRows}</ul></section>
        <section><h4>Najtańsze godziny zakupu</h4><ul>${buyRows}</ul></section>
      </div>
      <div class="analysis-explanation"><span>Powód sugestii</span><strong>${reason}</strong></div>
      <div class="analysis-explanation"><span>Wynik i skuteczność</span><strong>${outcome}</strong></div>
    </div>`;
  }

  renderHistoryTab() {
    const data = this.historyData();
    const filters = this._historyFilters || { from: "", to: "", type: "all" };
    const inRange = (date) => (!filters.from || date >= filters.from) && (!filters.to || date <= filters.to);
    const analyses = this.filteredAnalyses();
    const daily = data.daily.filter((item) => inRange(String(item.date || "")));
    const monthly = data.monthly.filter((item) => inRange(`${item.month || ""}-01`));
    const eventLabel = (event) => this.escapeHtml(({ suggestion: "Sugestia", accepted: "Zaakceptowana", daily_summary: "Podsumowanie dnia" }[event] || event || "Sugestia"));
    const analysisRows = analyses.length ? analyses.map((item) => {
      const date = new Date(Number(item.timestamp) || item.date || 0);
      const dateLabel = Number.isNaN(date.getTime()) ? (item.date || "brak") : date.toLocaleString("pl-PL");
      const sell = item.bestSell?.[0] ? `${this.hourLabel(item.bestSell[0][0])} · ${this.formatPrice(item.bestSell[0][1])} PLN` : "brak";
      const outcome = item.event === "daily_summary" ? `Trafność ${this.formatNumber(item.accuracy_percent, 1)}%` : item.outcome ? `${this.formatNumber(item.outcome.sold_kwh, 2)} kWh / ${this.formatNumber(item.outcome.sold_value, 2)} PLN · PV ${this.formatNumber(item.outcome.pv_accuracy_percent, 0)}%` : item.rating ? `Ocena ${item.rating}/5` : item.event === "accepted" ? "Oczekuje na wynik dnia" : "Nie zastosowano";
      const rating = item.event === "accepted" || item.event === "suggestion" ? `<span class="history-rating">${[1,2,3,4,5].map((value) => `<button data-rate-history="${item.timestamp}" data-rating="${value}" class="${Number(item.rating) === value ? "active" : ""}">${value}</button>`).join("")}</span>` : "";
      return `<tr><td>${this.escapeHtml(dateLabel)}</td><td>${eventLabel(item.event)}</td><td>${sell}</td><td>${outcome}<br>${rating}</td><td></td></tr>
        <tr class="analysis-detail-row"><td colspan="5"><details class="analysis-record"><summary>Szczegóły</summary>${this.renderAnalysisDetails(item)}</details></td></tr>`;
    }).join("") : `<tr><td colspan="5">Brak rekordów dla wybranych filtrów</td></tr>`;
    const dailyRows = daily.length ? daily.map((item) => {
      const currentRealization = this.asNumber(item.realization_today_pct ?? item.forecast_progress_percent);
      const accuracy = item.accuracy_percent === null || item.accuracy_percent === undefined
        ? (currentRealization === null ? "W toku (brak danych)" : `W toku (${this.formatNumber(currentRealization, 1)}% realizacji)`)
        : `${this.formatNumber(item.accuracy_percent, 1)}%`;
      return `<tr><td>${item.date}</td><td>${this.formatNumber(item.forecast_kwh, 2)}</td><td>${this.formatNumber(item.actual_kwh ?? item.pv_kwh, 2)}</td><td>${accuracy}</td><td>${this.formatNumber(item.load_kwh, 2)}</td><td>${this.formatNumber(item.battery_charge_kwh, 2)} / ${this.formatNumber(item.battery_discharge_kwh, 2)}</td><td>${this.formatNumber(item.sold_kwh, 2)} / ${this.formatNumber(item.sold_value, 2)} PLN</td></tr>`;
    }).join("") : `<tr><td colspan="7">Brak podsumowań dziennych</td></tr>`;
    const monthlyRows = monthly.length ? monthly.map((item) => `<tr><td>${item.month}</td><td>${item.days}</td><td>${this.formatNumber(item.pv_kwh, 1)}</td><td>${this.formatNumber(item.load_kwh, 1)}</td><td>${this.formatNumber(item.grid_import_kwh, 1)} / ${this.formatNumber(item.grid_export_kwh, 1)}</td><td>${this.formatNumber(item.sold_kwh, 1)} / ${this.formatNumber(item.sold_value, 2)} PLN</td></tr>`).join("") : `<tr><td colspan="6">Brak podsumowań miesięcznych</td></tr>`;
    return `<div class="history-toolbar">
      <label>Od<input type="date" data-history-filter="from" value="${filters.from || ""}"></label>
      <label>Do<input type="date" data-history-filter="to" value="${filters.to || ""}"></label>
      <label>Typ<select data-history-filter="type"><option value="all">Wszystkie</option><option value="suggestion" ${filters.type === "suggestion" ? "selected" : ""}>Sugestie</option><option value="accepted" ${filters.type === "accepted" ? "selected" : ""}>Zaakceptowane</option><option value="daily_summary" ${filters.type === "daily_summary" ? "selected" : ""}>Podsumowania dnia</option></select></label>
      <button data-export-history="csv">Eksport CSV</button><button data-export-history="json">Eksport JSON</button><button data-export-monthly="1">Raport miesięczny</button>
    </div>
    <section class="history-section"><h3>Prognoza i rzeczywista produkcja</h3><div class="history-scroll"><table class="settings-table"><thead><tr><th>Data</th><th>Prognoza kWh</th><th>Produkcja kWh</th><th>Trafność / stan</th><th>Dom kWh</th><th>Ład./rozł. kWh</th><th>Sprzedaż</th></tr></thead><tbody>${dailyRows}</tbody></table></div></section>
    <section class="history-section"><h3>Wcześniejsze sugestie i skuteczność</h3><div class="history-scroll analysis-history-scroll"><table class="settings-table analysis-history-table"><thead><tr><th>Data</th><th>Typ</th><th>Najlepsza sprzedaż</th><th>Wynik / ocena</th><th>Rekord</th></tr></thead><tbody>${analysisRows}</tbody></table></div></section>
    <section class="history-section"><h3>Podsumowania miesięczne</h3><div class="history-scroll"><table class="settings-table"><thead><tr><th>Miesiąc</th><th>Dni</th><th>PV kWh</th><th>Dom kWh</th><th>Import / eksport</th><th>Sprzedaż</th></tr></thead><tbody>${monthlyRows}</tbody></table></div></section>
    <button class="danger-action" data-clear-all-history="1">Wyczyść historię i dane</button>`;
  }

  renderDialog(slots, touStarts) {
    if (!this._dialog) return "";

    if (this._dialog.type === "settings") {
      const tab = this._settingsTab || "defaults";
      const tabButton = (key, label) => `<button class="${tab === key ? "active" : ""}" data-settings-tab="${key}">${label}</button>`;
      const aiSettings = this.aiSettings();
      const segments = this.scheduleSegments(slots);
      const segmentRows = segments.map((item, index) => `<tr>
          <td>${index + 1}</td>
          <td>${String(item.start).padStart(2, "0")}:00</td>
          <td>${String(item.end).padStart(2, "0")}:00</td>
          <td>${item.chargeEnabled ? "tak" : "nie"}</td>
          <td>${item.touSoc === null ? "wymaga potwierdzenia" : `${item.touSoc}%`}</td>
        </tr>`).join("");

      let body = "";
      if (tab === "defaults") {
        body = `
          <h3>Ustawienia domyślne dla falownika</h3>
          <div class="hint">Te wartości są automatycznie stosowane po Stop Sell, zatrzymaniu awaryjnym albo błędzie sterowania. Ustaw tutaj konfigurację bezpieczną dla swojej instalacji.</div>
          ${this.row("Domyślny tryb Managera", this.rawSelect("default-work-mode", this.defaultWorkModes(), this.defaultSettingsMode()))}
          ${this.row("Fizyczny wariant Normalnej Pracy", this.rawSelect("default-physical-work-mode", [["", "-- wybierz --"], ...this.normalProfileModeOptions()], this.defaultPhysicalWorkMode()))}
          ${this.row("Domyślna maksymalna moc sprzedaży", this.defaultProfileInput("sell_power", this.entity("number", "default_sell_power"), "W"))}
          ${this.row("Domyślny prąd rozładowania", this.defaultProfileInput("discharge_current", this.entity("number", "default_discharge_current"), "A"))}
          ${this.row("Domyślny prąd ładowania baterii", this.defaultProfileInput("charge_current", this.entity("number", "default_charge_current"), "A"))}
          ${this.row("Domyślny prąd ładowania z sieci", this.defaultProfileInput("grid_charge_current", this.entity("number", "default_grid_charge_current"), "A"))}
          <div class="hint">Stan powrotu: ${this.escapeHtml(this.state(this.entity("select", "default_work_mode")))} · ${this.escapeHtml(this.state(this.entity("number", "default_sell_power")))} W · rozładowanie ${this.escapeHtml(this.state(this.entity("number", "default_discharge_current")))} A · ładowanie ${this.escapeHtml(this.state(this.entity("number", "default_charge_current")))} A · sieć ${this.escapeHtml(this.state(this.entity("number", "default_grid_charge_current")))} A</div>
          <button class="wide-action" data-save-default-settings="1">Zapisz ustawienia domyślne</button>
          <button class="wide-action" data-action="apply-defaults" data-default-action="1" data-default-label="Zastosuj ustawienia domyślne teraz" ${this._defaultsApplying ? "disabled" : ""}>${this._defaultsApplying ? "Stosowanie ustawień domyślnych…" : "Zastosuj ustawienia domyślne teraz"}</button>
          <h3>Ustawienia ładowania</h3>
          <div class="hint">To szablon kopiowany do slotu w chwili wybrania trybu <strong>Ładowanie</strong>. Późniejsze ręczne zmiany w tym slocie mają pierwszeństwo i nie są nadpisywane kolejnym zapisem szablonu.</div>
          ${this.row("Tryb ładowania", "Ładowanie")}
          ${this.row("Ładowanie z sieci", this.rawSelect("charge-profile-grid", [["on", "TAK"], ["off", "NIE"]], this.chargeProfileGridEnabled() ? "on" : "off"))}
          ${this.row("Prąd ładowania", this.chargeProfileInput("charge_current", this.entity("number", "charge_profile_charge_current"), "A"))}
          ${this.row("Prąd rozładowania", this.chargeProfileInput("discharge_current", this.entity("number", "charge_profile_discharge_current"), "A"))}
          ${this.row("Prąd ładowania z sieci", this.chargeProfileInput("grid_charge_current", this.entity("number", "charge_profile_grid_charge_current"), "A"))}
          ${this.row("Docelowy SOC", this.chargeProfileInput("target_soc", this.entity("number", "charge_profile_target_soc"), "%"))}
          <div class="hint">Ładowanie z sieci: NIE — bateria może ładować się z PV. Ładowanie z sieci: TAK — jest dozwolone wyłącznie w zakresach trybu Ładowanie.</div>
          <button class="wide-action" data-save-charge-profile="1">Zapisz ustawienia ładowania</button>
          <h3>Ustawienia normalnej pracy</h3>
          <div class="hint">Ten szablon jest kopiowany do slotu tylko w chwili wybrania trybu <strong>Normalna Praca</strong>. Późniejsze ręczne zmiany w danym slocie mają pierwszeństwo i nie są automatycznie nadpisywane zmianami szablonu.</div>
          ${this.row("Tryb normalnej pracy", this.rawSelect("normal-profile-mode", [["", "-- wybierz --"], ...this.normalProfileModeOptions()], this.normalProfileMode()))}
          ${this.row("Maksymalna moc sprzedaży", this.normalProfileInput("sell_power", this.entity("number", "normal_profile_sell_power"), "W"))}
          ${this.row("Maksymalny prąd rozładowania", this.normalProfileInput("discharge_current", this.entity("number", "normal_profile_discharge_current"), "A"))}
          ${this.row("Maksymalny prąd ładowania baterii", this.normalProfileInput("charge_current", this.entity("number", "normal_profile_charge_current"), "A"))}
          ${this.row("Maksymalny prąd ładowania z sieci", this.normalProfileInput("grid_charge_current", this.entity("number", "normal_profile_grid_charge_current"), "A"))}
          ${this.row("SOC baterii Deye (TOU)", this.normalProfileInput("tou_soc", this.entity("number", "normal_profile_tou_soc"), "%"))}
          <div class="hint">Fizyczny SOC zapisywany do Deye Time Of Use dla slotów Normalnej Pracy. Nie jest to minimalny SOC sprzedaży.</div>
          <button class="wide-action" data-save-normal-profile="1">Zapisz ustawienia normalnej pracy</button>
          <div class="hint defaults-status ${this._defaultsStatus}" data-defaults-status ${this._defaultsMessage ? "" : "hidden"}>${this.escapeHtml(this._defaultsMessage)}</div>`;
      } else if (tab === "tou") {
        body = this.renderTouSettingsContent();
      } else if (tab === "mapping") {
        body = `<div class="hint">${this.mapWarning(slots)}. Harmonogram 24 h jest układany w sześć zakresów i zapisywany do Deye Time Of Use.</div>
          <table class="settings-table"><thead><tr><th>Slot Deye</th><th>Od</th><th>Do</th><th>Ładowanie z sieci</th><th>SOC</th></tr></thead><tbody>${segmentRows}</tbody></table>`;
      } else if (tab === "ai") {
        body = this.renderAiSettingsPanel();
      } else if (tab === "tariff") {
        body = this.renderTariffTab();
      } else if (tab === "history") {
        body = this.renderHistoryTab();
      } else if (tab === "system") {
        body = this.renderDiagnostics(slots);
      }

      return `<div class="overlay" data-close-dialog="1">
        <section class="dialog settings-dialog" data-dialog-box="1">
          <div class="dialog-head"><strong>Ustawienia i diagnostyka</strong><button type="button" data-close-dialog="1">${this.iconSvg("close")}</button></div>
          <div class="settings-layout">
            <nav class="settings-nav">
              ${tabButton("defaults", "Ustawienia Trybów")}
              ${tabButton("tou", "Deye Time Of Use")}
              ${tabButton("mapping", "Mapowanie 24h")}
              ${tabButton("ai", "AI i analiza")}
              ${tabButton("tariff", "Taryfa i dystrybucja")}
              ${tabButton("history", "Historia i dane")}
              ${tabButton("system", "System i diagnostyka")}
            </nav>
            <div class="settings-content">${body}</div>
          </div>
        </section>
      </div>`;
    }

    if (this._dialog.type === "ai") {
      return this.renderAiDialog(slots);
    }

    if (this._dialog.type === "multi") {
      const selectedCount = this.selectedSlotList(slots).length;
      const bulk = this.bulkValues(slots);
      return `<div class="overlay" data-close-dialog="1">
        <section class="dialog multi-dialog" data-dialog-box="1">
          <div class="dialog-head"><strong>Edytuj zaznaczone godziny</strong><button type="button" data-close-dialog="1">${this.iconSvg("close")}</button></div>
          <div class="dialog-body">
            <div class="range-box">Zakres: ${this.selectedRangeText(slots)}<br>Liczba godzin: ${selectedCount}</div>
            <label class="apply-row"><input type="checkbox" data-apply-field="active" checked> Aktywne ${this.rawSelect("multi-active", [["on", "Tak"], ["off", "Nie"]], bulk.active)}</label>
              <label class="apply-row"><input type="checkbox" data-apply-field="mode" checked> Tryb pracy ${this.rawSelect("multi-mode", this.slotModeOptions(), bulk.mode)}</label>
            <label class="apply-row"><input type="checkbox" data-apply-field="sellPower" checked> Moc sprzedaży ${this.rawNumber("multi-sell-power", bulk.sellPower, "W")}</label>
            <label class="apply-row"><input type="checkbox" data-apply-field="dischargeCurrent" checked> Prąd rozładowania ${this.rawNumber("multi-discharge-current", bulk.dischargeCurrent, "A")}</label>
            <label class="apply-row"><input type="checkbox" data-apply-field="chargeCurrent" checked> Prąd ładowania ${this.rawNumber("multi-charge-current", bulk.chargeCurrent, "A")}</label>
            <label class="apply-row"><input type="checkbox" data-apply-field="minSoc" checked> Minimalny SOC sprzedaży ${this.rawNumber("multi-min-soc", bulk.minimumSellSoc, "%")}</label>
            <label class="apply-row"><input type="checkbox" data-apply-field="minSellPrice" checked> Sprzedawaj od ceny ${this.rawNumber("multi-min-sell-price", bulk.minSellPrice, "PLN")}</label>
            <div class="preview-box"><strong>Podgląd zmian</strong><br>Wartości startowe są pobrane z pierwszej zaznaczonej godziny. Odznacz pole, którego nie chcesz zmieniać.</div>
          </div>
          <div class="dialog-actions"><button type="button" data-close-dialog="1">Anuluj</button><button class="primary" data-apply-multi="1">Zastosuj zmiany</button></div>
        </section>
      </div>`;
    }

    if (this._dialog.type === "tou") {
      const idx = Number(this._dialog.idx);
      const capability = this.touCapabilityRow(idx);
      const supportedFields = this.touFieldNames().filter((field) => capability?.fields?.[field]?.supported === true);
      this.ensureTouEditorDraft(idx);
      const hasWritableField = supportedFields.some((field) => capability.fields?.[field]?.writable === true);
      const readOnly = capability?.read_only === true || !hasWritableField;
      const blockedByControl = this.touControlBlocked(capability);
      const pending = this._touSaving || this.touWritePending();
      const blockMessage = blockedByControl
        ? "Sterowanie Deye jest wyłączone."
        : pending ? "Trwa zapis Deye Time Of Use" : "";
      const fields = supportedFields.map((field) => this.touEditorFieldHtml(idx, field)).join("");
      const noFields = !supportedFields.length
        ? `<div class="hint">Brak dostępnych pól Deye Time Of Use dla tego providera.</div>`
        : "";
      const readOnlyMessage = capability?.read_only === true
        ? `<div class="hint">Ten provider udostępnia Deye Time Of Use tylko do odczytu.</div>`
        : "";
      const saveButton = !readOnly && supportedFields.length
        ? `<button class="primary" type="button" data-save-tou="${idx}" ${blockedByControl || pending ? "disabled" : ""} title="${this.escapeHtml(blockMessage)}">${pending ? "Zapisywanie…" : "Zapisz"}</button>`
        : "";
      const error = this._touSaveError || (["rollback", "rollback_failed", "mismatch", "unavailable"].includes(this.touOperationStatus()) ? this.touOperationError() : "");
      return `<div class="overlay" data-close-dialog="1">
        <section class="dialog" data-dialog-box="1">
          <div class="dialog-head"><strong>Deye Time Of Use - slot ${idx}</strong><button type="button" data-close-dialog="1">${this.iconSvg("close")}</button></div>
          <div class="dialog-body">
            ${noFields}${readOnlyMessage}${fields}
            <div class="hint">Status operacji: <strong>${this.touOperationStatusLabel()}</strong></div>
            ${blockMessage ? `<div class="hint">${blockMessage}</div>` : ""}
            ${error ? `<div class="bad" data-tou-save-error>${this.escapeHtml(String(error))}</div>` : ""}
            ${this.renderTouReverseSyncSummary()}
          </div>
          <div class="dialog-actions"><button type="button" data-close-dialog="1">${readOnly ? "Zamknij" : "Anuluj"}</button>${saveButton}</div>
        </section>
      </div>`;
    }

    const slot = slots.find(([key]) => key === this._dialog.key);
    if (!slot) return "";
    const [key, label] = slot;
    this.ensureSlotEditor(key, label);
    if (this._slotDiscardPrompt) {
      return `<div class="overlay">
        <section class="dialog" data-dialog-box="1">
          <div class="dialog-head"><strong>Niezapisane zmiany</strong></div>
          <div class="dialog-body"><div class="hint">Masz niezapisane zmiany. Czy na pewno chcesz je odrzucić?</div></div>
          <div class="dialog-actions"><button type="button" data-return-slot-edit="1">Wróć do edycji</button><button class="primary" type="button" data-discard-slot-edit="1">Odrzuć zmiany</button></div>
        </section>
      </div>`;
    }
    const draft = this._slotEditDraft.values;
    const mode = this.normalizeManagerMode(draft.mode || "Normalna Praca");
    const isCharge = mode === "Ładowanie";
    const isSelling = mode === "Sprzedaż";
    const isNormal = mode === "Normalna Praca";
    const physicalSocLabel = isCharge ? "Docelowy SOC" : "SOC baterii Deye (TOU)";
    const yesNo = [["false", "Nie"], ["true", "Tak"]];
    const socField = isSelling
      ? `${this.row("Zatrzymaj sprzedaż przy SOC", this.slotDraftInput("minimum_sell_soc", "%"))}${this.row("SOC Deye TOU / rezerwa baterii", this.slotDraftInput("tou_soc", "%"))}`
      : this.row(physicalSocLabel, this.slotDraftInput("tou_soc", "%"));
    const slotFields = `
          ${isCharge ? '<div class="hint">Wartości profilu ładowania zostały podłożone wyłącznie do lokalnego draftu. Zapis nastąpi dopiero po wybraniu „Zapisz”.</div>' : ""}
          ${isCharge ? `<button class="primary" type="button" data-draft-charge-profile="1" style="margin-bottom:8px">Wczytaj ponownie ustawienia ładowania</button>` : ""}
          ${isNormal ? '<div class="hint">Wartości profilu Normalnej Pracy są edytowane lokalnie do chwili zapisu.</div>' : ""}
          ${isNormal ? `<button class="primary" type="button" data-draft-normal-profile="1" style="margin-bottom:8px">Wczytaj ponownie ustawienia normalnej pracy</button>` : ""}
          ${isNormal ? this.row("Fizyczny tryb Deye", this.slotDraftSelect("physical_work_mode", this.normalProfileModeOptions())) : ""}
          ${this.row("Moc sprzedaży", this.slotDraftInput("sell_power", "W"))}
          ${this.row("Prąd rozładowania", this.slotDraftInput("discharge_current", "A"))}
          ${this.row("Prąd ładowania baterii", this.slotDraftInput("charge_current", "A"))}
          ${this.row("Ładowanie z sieci", this.slotDraftSelect("charge_enabled", yesNo))}
          ${this.row("Prąd ładowania z sieci", this.slotDraftInput("grid_charge_current", "A"))}
          ${socField}
          ${this.row("Sprzedawaj od ceny", this.slotDraftInput("min_sell_price", "PLN"))}`;
    return `<div class="overlay" data-close-dialog="1">
      <section class="dialog" data-dialog-box="1">
        <div class="dialog-head"><strong>Godzina ${label}</strong><button type="button" data-close-dialog="1">${this.iconSvg("close")}</button></div>
        <div class="dialog-body">
          ${this.row("Aktywne", this.slotDraftSelect("enabled", yesNo))}
          ${this.row("Tryb", this.slotDraftSelect("mode", this.slotModeOptions()))}
          ${slotFields}
          ${this._slotSaveError ? `<div class="bad" data-slot-save-error>${this.escapeHtml(this._slotSaveError)}</div>` : ""}
          ${this._slotSaveMessage ? `<div class="hint">${this.escapeHtml(this._slotSaveMessage)}</div>` : ""}
        </div>
        <div class="dialog-actions"><button type="button" data-cancel-slot-edit="1" ${this._slotSaving ? "disabled" : ""}>Anuluj</button><button class="primary" type="button" data-save-slot-edit="1" ${this._slotSaving ? "disabled" : ""}>${this._slotSaving ? "Zapisywanie…" : "Zapisz"}</button></div>
      </section>
    </div>`; 
  }

  renderV073() {
    if (!this._hass) return;
    this._pendingRender = false;
    this.captureScrollPositions();

    const slots = this.scheduleSlots();
    const activeSlot = this.state(this.entity("sensor", "active_slot"));
    const activeSlotLabel = (slots.find(([key]) => key === activeSlot)?.[1] || activeSlot).replace(/:00/g, "");
    const [modeText, modeClass] = this.readMode(this.state(this.entity("sensor", "manager_status")));
    const currentInverterMode = this.state(this.entity("sensor", "current_work_mode"));
    const targetInverterMode = this.state(this.entity("sensor", "target_mode"));
    const decisionText = this.state(this.entity("sensor", "decision_reason"));
    const control = this.controlState();
    const masterControl = control.entity_id;
    const masterControlOn = control.enabled;
    const controlStatus = control.status;

    const batterySoc = this.entity("sensor", "battery_soc");
    const soldEnergyToday = this.entity("sensor", "sold_energy_today");
    const soldValueToday = this.entity("sensor", "sold_value_today");
    const sellPriceToday = this.entity("sensor", ["sell_price_today", "energy_price"]);
    const sellPriceTomorrow = this.entity("sensor", "sell_price_tomorrow");
    const buyPriceToday = this.entity("sensor", "buy_price_today");
    const buyPriceTomorrow = this.entity("sensor", "buy_price_tomorrow");
    const solcastPower = this.entity("sensor", "solcast_current_power");
    const solcastToday = this.entity("sensor", "solcast_forecast_today");
    const solcastTomorrow = this.entity("sensor", "solcast_forecast_tomorrow");
    const solcastDay3 = this.entity("sensor", "solcast_forecast_day_3");
    const solcastDay4 = this.entity("sensor", "solcast_forecast_day_4");
    const solcastDay5 = this.entity("sensor", "solcast_forecast_day_5");
    const solcastDay6 = this.entity("sensor", "solcast_forecast_day_6");
    const solcastDay7 = this.entity("sensor", "solcast_forecast_day_7");
    const solcastRemaining = this.entity("sensor", "solcast_remaining_today");
    const solcastPeakPower = this.entity("sensor", "solcast_peak_power_today");
    const dailyPvProduction = this.entity("sensor", "daily_pv_production");
    const solcastAccuracy = this.entity("sensor", "solcast_accuracy");
    const minSellPrice = this.entity("number", "minimum_sell_price");
    const priceThreshold = this.asNumber(this.numberState(minSellPrice, 0)) || 0;
    const solcastEntities = [solcastToday, solcastTomorrow, solcastDay3, solcastDay4, solcastDay5, solcastDay6, solcastDay7];
    const solcastAccuracyAttrs = this._hass?.states?.[solcastAccuracy]?.attributes || {};
    const solcastForecastValue = this.asNumber(solcastAccuracyAttrs.forecast_today_kwh);
    const dailyPvValue = this.asNumber(solcastAccuracyAttrs.production_today_kwh);
    const solcastDifference = this.asNumber(solcastAccuracyAttrs.forecast_difference_today_kwh);
    const realizationTodayValue = this.asNumber(solcastAccuracyAttrs.realization_today_pct);
    const historicalAccuracyValue = this.asNumber(solcastAccuracyAttrs.historical_accuracy_pct)
      ?? this.asNumber(this.state(solcastAccuracy));
    const remainingForecastValue = this.asNumber(solcastAccuracyAttrs.remaining_forecast_kwh);
    const forecastTomorrowValue = this.asNumber(solcastAccuracyAttrs.forecast_tomorrow_kwh);

    const physicalTou = this.physicalTouDiagnostics();
    const touStarts = [1, 2, 3, 4, 5, 6].map((idx) => {
      const diagnostic = physicalTou.find((row) => Number(row.range) === idx);
      const raw = diagnostic?.actual_start || "00:00:00";
      return String(raw).length >= 5 ? String(raw).slice(0, 5) : String(raw);
    });

    const selectedCount = this.selectedSlotList(slots).length;
    const bulk = { ...this.bulkValues(slots), ...(this._bulkEditDraft || {}) };
    const bulkFieldChecked = (name) => this._bulkEditFields?.[name] !== false;
    const scheduleRows = slots.map(([key, label]) => {
      const entities = this.slotEntities(key, label);
      const enabled = this.displayState(entities.sellEnabled) === "on";
      const mode = this.normalizeManagerMode(this.displayState(entities.mode, "Normalna Praca"));
      const gridChargeState = this.displayState(entities.chargeEnabled, "");
      const gridCharge = gridChargeState === "on";
      const isChargeMode = mode === "Ładowanie";
      const gridChargeLabel = isChargeMode ? (gridCharge ? "tak" : "nie") : "nie dotyczy";
      const gridChargeClass = isChargeMode ? (gridCharge ? "on" : "off") : "missing";
      const chargeCurrent = this.numberState(entities.chargeCurrent);
      const gridChargeCurrent = this.numberState(entities.gridChargeCurrent);
       // Physical Deye TOU SOC is always the user-owned tou_soc, also for Sprzedaż.
      const touSoc = this.numberState(entities.touSoc, "wymaga potwierdzenia");
      const selected = this._selectedSlots?.has(key);
      const meta = this.modeMeta(mode, enabled);
      const rowClass = [
        activeSlot === key ? "active" : "",
        selected ? "selected" : "",
        enabled ? "enabled" : "disabled",
      ].filter(Boolean).join(" ");
      return `<tr class="${rowClass}" data-slot-row="${key}">
        <td class="check-col" data-label=""><label class="slot-check"><input type="checkbox" data-slot-check="${key}" ${selected ? "checked" : ""}><span></span></label></td>
        <td data-label="Godzina" class="time-col">${label.replace(/:00/g, "")}</td>
        <td data-label="Tryb">${this.modePill(mode, enabled)}</td>
        <td data-label="Moc sprzedaży" class="metric sell">${enabled ? `${this.iconSvg("sell")} ${this.numberState(entities.sellPower)} W` : "-"}</td>
        <td data-label="Prąd rozładowania" class="metric discharge">${enabled ? `↓ ${this.numberState(entities.dischargeCurrent)} A` : "-"}</td>
        <td data-label="Prąd ładowania" class="metric charge">${enabled ? `↑ ${chargeCurrent} A` : "-"}</td>
        <td data-label="Ładowanie z sieci" class="metric grid">${enabled ? `<span class="pill ${gridChargeClass}">${gridChargeLabel}</span>` : "-"}</td>
        <td data-label="Prąd ładowania z sieci" class="metric grid-current">${enabled ? `⚡ ${gridChargeCurrent} A` : "-"}</td>
        <td data-label="SOC" class="metric soc">${enabled ? `◇ ${touSoc}%` : "-"}</td>
        <td data-label="Cena min." class="metric price-limit">${enabled ? `${this.formatPrice(this.numberState(entities.minSellPrice))} PLN` : "-"}</td>
        <td data-label="Aktywne">${this.pill(entities.sellEnabled, enabled ? "ON" : "OFF")}</td>
        <td data-label="Akcja"><button class="icon-only" data-open-slot="sell:${key}" title="Edytuj">${this.iconSvg("edit")}</button></td>
      </tr>`;
    }).join("");

    const selectedInfo = this._selectionMode ? `<aside class="bulk-panel">
      <h3>Edytuj zaznaczone godziny</h3>
      <div class="range-box">
        <strong>Zakres: ${this.selectedRangeText(slots)}</strong>
        <span>Liczba godzin: ${selectedCount}</span>
        <small>${this.mapWarning(slots)}</small>
      </div>
      <label class="apply-row"><input type="checkbox" data-apply-field="active" ${bulkFieldChecked("active") ? "checked" : ""}><span>Aktywne</span>${this.rawSelect("multi-active", [["on", "Tak"], ["off", "Nie"]], bulk.active)}</label>
        <label class="apply-row"><input type="checkbox" data-apply-field="mode" ${bulkFieldChecked("mode") ? "checked" : ""}><span>Tryb pracy</span>${this.rawSelect("multi-mode", this.slotModeOptions(), bulk.mode)}</label>
      <label class="apply-row"><input type="checkbox" data-apply-field="sellPower" ${bulkFieldChecked("sellPower") ? "checked" : ""}><span>Moc sprzedaży</span>${this.rawNumber("multi-sell-power", bulk.sellPower, "W")}</label>
      <label class="apply-row"><input type="checkbox" data-apply-field="dischargeCurrent" ${bulkFieldChecked("dischargeCurrent") ? "checked" : ""}><span>Prąd rozładowania</span>${this.rawNumber("multi-discharge-current", bulk.dischargeCurrent, "A")}</label>
      <label class="apply-row"><input type="checkbox" data-apply-field="chargeCurrent" ${bulkFieldChecked("chargeCurrent") ? "checked" : ""}><span>Prąd ładowania</span>${this.rawNumber("multi-charge-current", bulk.chargeCurrent, "A")}</label>
      <label class="apply-row"><input type="checkbox" data-apply-field="minSoc" ${bulkFieldChecked("minSoc") ? "checked" : ""}><span>Minimalny SOC sprzedaży</span>${this.rawNumber("multi-min-soc", bulk.minSoc ?? bulk.minimumSellSoc, "%")}</label>
      <label class="apply-row"><input type="checkbox" data-apply-field="minSellPrice" ${bulkFieldChecked("minSellPrice") ? "checked" : ""}><span>Sprzedawaj od ceny</span>${this.rawNumber("multi-min-sell-price", bulk.minSellPrice, "PLN")}</label>
      <div class="preview-box"><strong>Podgląd zmian</strong><br>Wybrane pola zostaną wpisane tylko do zaznaczonych godzin. Pola bez znacznika zostają bez zmian.</div>
      <div class="bulk-actions"><button data-schedule-clear="1">${this.iconSvg("close")} Anuluj</button><button class="primary" data-apply-multi="1" ${selectedCount && !this._bulkApplying ? "" : "disabled"}>${this.iconSvg("check")} ${this._bulkApplying ? "Zapisywanie…" : "Zastosuj zmiany"}</button></div>
    </aside>` : "";

    const touRows = [1, 2, 3, 4, 5, 6].map((idx) => {
      const physical = physicalTou.find((row) => Number(row.range) === idx) || {};
      const end = physical.actual_end ? String(physical.actual_end).slice(0, 5) : "—";
      const start = physical.actual_start ? String(physical.actual_start).slice(0, 5) : "—";
      const soc = physical.actual_soc ?? "—";
      const grid = physical.actual_grid_charge ?? "—";
      return `<tr>
        <td data-label="Slot">${idx}</td>
        <td data-label="Od">${this.escapeHtml(start)}</td>
        <td data-label="Do">${this.escapeHtml(end)}</td>
        <td data-label="SOC Deye">${this.escapeHtml(String(soc))}${soc === "—" ? "" : " %"}</td>
        <td data-label="Ładowanie z sieci">${this.escapeHtml(this.touGridLabel(grid))}</td>
      </tr>`;
    }).join("");

    const layout = this.effectiveLayout();
    const dashStyle = [];
    dashStyle.push(layout.is_mobile ? "max-width:100%" : `max-width:${layout.dashboard_width}px`);
    dashStyle.push("min-width:0");
    dashStyle.push("box-sizing:border-box");
    if (layout.center_dashboard) dashStyle.push("margin:0 auto");
    if (layout.fit_to_width || layout.is_mobile) dashStyle.push("width:100%");
    if (layout.allow_horizontal_scroll) {
      dashStyle.push("overflow-x:auto");
    } else {
      dashStyle.push("overflow-x:hidden");
    }
    if (layout.layout_mode === "section" || layout.layout_mode === "single" || layout.layout_mode === "full" || layout.layout_mode === "fit") {
      dashStyle.push("grid-template-columns:1fr");
    } else if (layout.layout_mode === "grid" && layout.grid_columns) {
      dashStyle.push(`grid-template-columns:repeat(${layout.grid_columns},minmax(0,1fr))`);
      dashStyle.push(`gap:${layout.grid_gap}px`);
    }
    const demStyle = dashStyle.join(";");
    const infoGridStyle = layout.layout_mode === "grid"
      ? "display:contents"
      : (layout.is_mobile ? "grid-template-columns:minmax(0,1fr)" : `grid-template-columns:${layout.prices_ratio}fr ${layout.buy_prices_ratio}fr ${layout.solcast_ratio}fr`);

    const isSingle = layout.layout_mode === "single";
    const showStatus = isSingle ? layout.section === "status_energy" : layout.sections.status_energy;
    const showPrices = isSingle ? layout.section === "prices" : layout.sections.prices;
    const showBuyPrices = isSingle ? layout.section === "prices" : layout.sections.prices;
    const showSolcast = isSingle ? layout.section === "solcast" : layout.sections.solcast;
    const showSchedule = isSingle ? layout.section === "schedule" : layout.sections.schedule;
    const showSales = isSingle ? layout.section === "sales_stats" : layout.sections.sales_stats;
    if (isSingle && ["ai", "settings"].includes(layout.section) && !this._dialog) {
      this._dialog = { type: layout.section };
    }

    const statusSection = showStatus ? this.energyFlowPanel() : "";
    const pricesSection = showPrices ? `
             <section class="panel price-panel">
               <h2 class="panel-title">Ceny sprzedaży</h2>
               <div class="price-summary single">
                 ${this.stat("Teraz", `${this.formatPrice(this.state(sellPriceToday))} PLN/kWh`, "", "sell-now")}
               </div>
               ${this.priceTable(sellPriceToday, sellPriceTomorrow, priceThreshold, true, "sell-prices")}
             </section>` : "";
    const buyPricesSection = showBuyPrices ? `
             <section class="panel price-panel">
               <h2 class="panel-title">Ceny zakupu</h2>
               <div class="price-summary single">
                 ${this.stat("Teraz", `${this.formatPrice(this.state(buyPriceToday))} PLN/kWh`, "", "buy-now")}
               </div>
               ${this.priceTable(buyPriceToday, buyPriceTomorrow, 0, false, "buy-prices")}
             </section>` : "";
    const solcastSection = showSolcast ? `
             <section class="panel solcast-panel">
               <h2 class="panel-title">Prognoza Solcast</h2>
               <div class="solcast-summary">
                 ${this.stat("Teraz", this.formatPower(this.state(solcastPower)), "", "solcast-power")}
                 ${this.stat("Dziś", this.formatEnergy(solcastForecastValue), "", "solcast-today")}
                 ${this.stat("Pozostało", this.formatEnergy(remainingForecastValue), "", "solcast-remaining")}
                 ${this.stat("Jutro", this.formatEnergy(forecastTomorrowValue), "", "solcast-tomorrow")}
                 ${this.stat("Szczyt", this.formatPower(this.state(solcastPeakPower)), "", "solcast-peak-power")}
                 ${this.stat("Najlepszy dzień", this.bestSolcastDay(solcastEntities), "", "solcast-best-day")}
               </div>
               <div data-live-html="solcast-days">${this.solcastDaysChart(solcastEntities)}</div>
               <div data-live-html="solcast-chart">${this.solcastChart(solcastToday, solcastTomorrow)}</div>
               <div class="solcast-performance">
                 ${this.stat("Prognoza na dziś", this.formatEnergy(solcastForecastValue), "", "solcast-performance-forecast")}
                 ${this.stat("Produkcja rzeczywista", this.formatEnergy(dailyPvValue), "", "solcast-performance-actual")}
                 ${this.stat("Różnica", this.formatSignedEnergy(solcastDifference), "", "solcast-performance-difference")}
                 ${this.stat("Realizacja dzisiaj", realizationTodayValue === null ? "brak" : `${realizationTodayValue.toFixed(1)} %`, "", "solcast-performance-progress")}
                 ${this.stat("Trafność historyczna", historicalAccuracyValue === null ? "brak" : `${historicalAccuracyValue.toFixed(1)} %`, "", "solcast-performance-accuracy")}
               </div>
             </section>` : "";
    const infoGridSection = (showPrices || showBuyPrices || showSolcast) ? `
           <div class="info-grid" style="${infoGridStyle}">
            ${pricesSection}
            ${buyPricesSection}
            ${solcastSection}
           </div>` : "";
    const scheduleSection = showSchedule ? `
           <section class="schedule-shell">
             <div class="schedule-head">
               <div class="schedule-title">
                 <h2>Harmonogram pracy <button class="title-icon ai" data-open-ai="1" title="Sugestie AI">${this.iconSvg("ai")}</button><span class="save-indicator ${this._saveStatus}" data-save-indicator>${this._saveStatus === "saving" ? this._saveMessage || "Zapisywanie..." : this._saveStatus === "saved" ? this._saveMessage || "Zapisano" : this._saveStatus === "error" ? this._saveMessage : ""}</span></h2>
                 <p>Kliknij godzinę, aby edytować pojedynczy slot lub zaznacz wiele, aby edytować zbiorczo.</p>
                </div>
                <div class="schedule-tools">
                 <button class="tool-btn ${masterControlOn ? "active" : ""}" data-control-toggle="1" ${control.pending ? "disabled" : ""}>Sterowanie Deye — ${this.escapeHtml(controlStatus)}</button>
                 <button class="tool-btn ${this._selectionMode ? "active" : ""}" data-toggle-selection="1">${this.iconSvg("check")} Tryb zaznaczania</button>
                 <button class="tool-btn" data-schedule-select-all="1">${this.iconSvg("copy")} Zaznacz wszystko</button>
                 <button class="tool-btn" data-schedule-clear="1">${this.iconSvg("close")} Odznacz wszystko</button>
                 <button class="gear-btn" data-open-settings="1" title="Ustawienia">${this.iconSvg("gear")}</button>
               </div>
             </div>
             <div class="schedule-main ${this._selectionMode ? "selecting" : ""}">
               <div class="schedule-left">
                 <div class="mode-legend">${this.modeLegend()}</div>
                 <div class="schedule-table-card">
                   <table class="schedule-table">
                     <colgroup>
                       <col class="col-check"><col class="col-time"><col class="col-mode"><col class="col-power">
                       <col class="col-current"><col class="col-current"><col class="col-grid"><col class="col-grid-current">
                       <col class="col-soc"><col class="col-price"><col class="col-active"><col class="col-action">
                     </colgroup>
                     <thead><tr><th class="check-col"></th><th class="time-col">Godz.</th><th>Tryb</th><th>Moc</th><th>Rozł.</th><th>Ład.</th><th>Ładowanie z sieci</th><th>Prąd ładowania z sieci</th><th>SOC</th><th>Cena min.</th><th>Aktywne</th><th>Akcja</th></tr></thead>
                     <tbody>${scheduleRows}</tbody>
                   </table>
                   <div class="schedule-foot">
                     <span>Zaznaczonych: <strong>${selectedCount} godzin</strong></span>
                     <div class="foot-actions">
                       <button data-schedule-clear="1">${this.iconSvg("close")} Odznacz</button>
                       <button class="primary" data-open-multi="1" ${selectedCount ? "" : "disabled"}>${this.iconSvg("edit")} Edytuj zaznaczone (${selectedCount})</button>
                       <button data-open-settings="mapping">${this.iconSvg("copy")} Mapowanie Deye</button>
                     </div>
                   </div>
                 </div>
               </div>
               ${selectedInfo}
             </div>
           </section>` : "";
    const salesSection = showSales ? `
           <section class="panel sales-panel"><h2 class="panel-title">${this.iconSvg("chart")} Statystyki sprzedaży</h2><div data-live-html="sales-stats">${this.salesStatsPanel()}</div></section>` : "";

    this.innerHTML = `
      <ha-card class="theme-schedule-dark">
        <style>
          ha-card{--bg:#020b12;--panel:rgba(9,24,35,.92);--panel2:rgba(13,31,45,.88);--panel3:rgba(16,38,54,.72);--line:rgba(118,166,190,.22);--line2:rgba(80,169,226,.38);--text:#eef7ff;--muted:#9eb8c8;--blue:#159bff;--blue2:#0a6ad8;--green:#7ee22d;--green2:#35d66f;--purple:#bc63ff;--gold:#f6a619;--red:#ff4242;overflow:hidden;background:radial-gradient(circle at 18% 0%,rgba(26,106,164,.22),transparent 34%),linear-gradient(180deg,#020913,#06131c 54%,#050b10);color:var(--text);border:1px solid rgba(101,142,164,.32);box-shadow:0 18px 45px rgba(0,0,0,.35)}
 .dem-v073{padding:18px;display:grid;gap:16px;margin:0 auto;max-width:1280px;min-width:0;box-sizing:border-box;font-family:Roboto,Arial,sans-serif;font-size:14px}.dialog-host{position:relative}.dem-v073>*,.info-grid>*,.panel,.schedule-shell,.sales-panel{min-width:0;max-width:100%;box-sizing:border-box}
           svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
          button{font:inherit}
           .panel,.schedule-shell,.table-wrap{box-sizing:border-box;border:1px solid rgba(107,157,182,.34);border-radius:10px;background:radial-gradient(circle at 12% 8%,rgba(20,85,130,.16),transparent 32%),linear-gradient(180deg,rgba(5,16,26,.98),rgba(7,21,32,.98));box-shadow:inset 0 1px 0 rgba(255,255,255,.035),0 12px 28px rgba(0,0,0,.18)}
          .panel-title,.table-title{margin:0;padding:12px 14px;background:linear-gradient(180deg,rgba(16,45,61,.92),rgba(6,20,31,.86));border-bottom:1px solid rgba(107,157,182,.24);font-size:18px;font-weight:800;color:#fff}
          .status-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:10px}
          .stat{border:1px solid rgba(111,154,178,.45);border-radius:7px;background:rgba(7,18,28,.74);padding:10px;min-width:0}
          .stat span{display:block;color:#a9c1d0;font-size:12px}.stat strong{display:block;margin-top:4px;color:#fff;font-size:18px;line-height:1.2}.stat.good strong,.good{color:#2dff95!important}.stat.warn strong,.warn{color:#ffd95c!important}.bad{color:#ff6b7a!important}
           .info-grid{display:grid;grid-template-columns:0.85fr 0.85fr 1.30fr;gap:14px;align-items:stretch;width:100%;box-sizing:border-box}.info-grid>.panel{height:auto;min-height:470px;display:flex;flex-direction:column;min-width:0}
          .price-summary,.solcast-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:9px}.price-summary.single{grid-template-columns:1fr}.price-summary .stat strong,.solcast-summary .stat strong{font-size:14px}
          .price-scroll{height:auto;flex:0 0 auto;min-height:0;overflow:visible;border-top:1px solid var(--line);overscroll-behavior:contain}.price-table{width:100%;border-collapse:collapse;table-layout:fixed}.price-table th,.price-table td{padding:3px 8px;border-top:1px solid var(--line);font-size:11px;line-height:14px}.price-table th{position:sticky;top:0;z-index:1;background:rgba(18,42,59,.96);color:#d8f4ff;text-align:left}.price-table tbody tr.active{background:rgba(37,105,151,.32);box-shadow:inset 3px 0 0 var(--blue)}.price-table tbody tr.active td:first-child{color:#fff;font-weight:900}.price{font-weight:900;color:#e9f7ff}.price.good{color:#2dff95}.price.warn{color:#ffd95c}.price.missing{opacity:.55}
                     .solcast-days{display:grid;grid-template-columns:repeat(7,minmax(58px,1fr));gap:8px;padding:9px;border-top:1px solid var(--line)}.solcast-day{height:104px;border:1px solid var(--line);border-radius:8px;background:rgba(7,18,28,.72);display:grid;grid-template-rows:auto 1fr auto;gap:4px;padding:6px}.solcast-day-head{display:flex;justify-content:space-between;gap:4px}.solcast-day-head strong{font-size:11px;color:#e8f7ff;white-space:nowrap}.solcast-day-head em{font-style:normal;font-size:10px;color:#88a7bb}.solcast-day-meter{display:flex;align-items:end;justify-content:center;border-radius:6px;background:rgba(255,255,255,.03)}.solcast-day-meter span{width:34px;border-radius:8px 8px 2px 2px;background:linear-gradient(180deg,#ffd166,#39ef8d);min-height:8px}.solcast-day b{text-align:center;font-size:11px}.solcast-day.missing{opacity:.45}
                     .solcast-panel{width:100%;max-width:100%;min-width:0;overflow:hidden}.solcast-panel [data-live-html="solcast-days"],.solcast-panel [data-live-html="solcast-chart"]{width:100%;max-width:100%;min-width:0;overflow:hidden}.solcast-chart{height:170px;max-width:100%;min-width:0;overflow-x:hidden;border-top:1px solid var(--line);padding:10px 8px 0;box-sizing:border-box;overscroll-behavior:contain}.solcast-bars{height:146px;width:100%;max-width:100%;min-width:0;display:grid;grid-template-columns:repeat(24,minmax(0,1fr));gap:4px;align-items:end}.solcast-bar{height:146px;min-width:0;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:4px}.solcast-columns{height:128px;width:100%;display:flex;align-items:end;justify-content:center;gap:2px}.solcast-columns span{display:block;width:42%;border-radius:4px 4px 0 0;min-height:3px}.solcast-columns .today{background:#2dff95}.solcast-columns .tomorrow{background:#57b9ff}.solcast-bar.now .solcast-columns span{box-shadow:0 0 0 1px #ffd166 inset}.solcast-bar em{font-style:normal;font-size:10px;color:#89a5b5;writing-mode:vertical-rl;transform:rotate(180deg)}.solcast-legend{display:flex;gap:7px;padding:4px 10px 8px;color:#a9c1d0;font-size:12px}.solcast-legend span{width:10px;height:10px;border-radius:999px;display:inline-block}.solcast-legend .today{background:#2dff95}.solcast-legend .tomorrow{background:#57b9ff}.solcast-performance{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:auto;padding:9px;border-top:1px solid var(--line)}.solcast-performance .stat{padding:8px}.solcast-performance .stat strong{font-size:14px}.live-changed{animation:dem-live-pulse .45s ease-out}@keyframes dem-live-pulse{0%{color:#fff;text-shadow:0 0 10px rgba(87,185,255,.9)}100%{color:inherit;text-shadow:none}}
          .defaults-status{margin-top:10px}.defaults-status.saving{color:#ffd166}.defaults-status.saved{color:var(--green)}.defaults-status.error{color:#ff8b98}button[data-default-action]:disabled{opacity:.55;cursor:wait}
           .schedule-shell{width:100%;max-width:100%;min-width:0;box-sizing:border-box;overflow:hidden;padding:10px;background:radial-gradient(circle at 12% 8%,rgba(20,85,130,.22),transparent 30%),linear-gradient(180deg,rgba(5,16,26,.98),rgba(7,21,32,.98))}
          .schedule-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:8px}.schedule-title h2{margin:0;display:flex;align-items:center;gap:8px;font-size:22px;font-weight:850}.schedule-title p{margin:3px 0 0;color:#c1d4df;font-size:13px}.title-icon{width:28px;height:28px;border-radius:999px;border:1px solid rgba(142,181,202,.42);background:rgba(255,255,255,.03);color:#d9ecf6;display:inline-flex;align-items:center;justify-content:center;cursor:pointer}.title-icon.ai{color:#2fa8ff}.title-icon:hover{border-color:var(--blue);color:#fff}.save-indicator{display:none;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:800;line-height:1.2}.save-indicator.saving{display:inline-flex;color:#ffd166;background:rgba(246,166,25,.16)}.save-indicator.saved{display:inline-flex;color:var(--green);background:rgba(53,214,111,.14)}.save-indicator.error{display:inline-flex;max-width:360px;color:#ff8b98;background:rgba(255,77,99,.15);white-space:normal}
          .schedule-tools{display:flex;gap:9px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.tool-btn,.gear-btn,.bulk-actions button,.set-btn,.icon-only{border:1px solid rgba(100,145,170,.42);border-radius:8px;background:rgba(7,17,27,.72);color:#eaf7ff;min-height:38px;padding:0 13px;display:inline-flex;align-items:center;gap:9px;cursor:pointer}.tool-btn.active{border-color:var(--blue);color:#2ea7ff;background:rgba(8,53,92,.55)}.gear-btn{width:48px;justify-content:center;padding:0}.gear-btn:hover,.tool-btn:hover,.set-btn:hover,.icon-only:hover{border-color:var(--blue);box-shadow:0 0 0 1px rgba(21,155,255,.25) inset}.icon-only{width:32px;min-height:28px;padding:0;justify-content:center}.set-btn{min-height:29px;padding:0 12px;font-weight:800}
          .mode-legend{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:4px 0 8px}.mode-tile{display:flex;align-items:center;gap:8px;min-width:0}.mode-icon{width:32px;height:32px;border-radius:11px;display:flex;align-items:center;justify-content:center;flex:0 0 auto}.mode-tile.selling .mode-icon{background:rgba(126,226,45,.16);color:var(--green)}.mode-tile.zero .mode-icon{background:rgba(21,155,255,.16);color:var(--blue)}.mode-tile.ct .mode-icon{background:rgba(188,99,255,.18);color:var(--purple)}.mode-tile.charge .mode-icon{background:rgba(246,166,25,.18);color:var(--gold)}.mode-tile.disabled .mode-icon{background:rgba(155,178,193,.12);color:#b9c9d4}.mode-tile.normal .mode-icon{background:rgba(77,171,247,.16);color:#4dabf7}.mode-tile strong{display:block;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mode-tile.selling strong{color:var(--green)}.mode-tile.zero strong{color:var(--blue)}.mode-tile.ct strong{color:var(--purple)}.mode-tile.charge strong{color:var(--gold)}.mode-tile.normal strong{color:#4dabf7}.mode-tile span{display:block;color:#c2d4de;margin-top:1px;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
           .schedule-main{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}.schedule-main.selecting{grid-template-columns:minmax(0,1fr) 340px}.schedule-left{min-width:0}.schedule-table-card{width:100%;max-width:100%;min-width:0;box-sizing:border-box;border:1px solid rgba(107,157,182,.28);border-radius:8px;overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;background:rgba(6,19,29,.62)}.schedule-table{width:100%;border-collapse:collapse;table-layout:auto}.schedule-table th,.schedule-table td{padding:1px 4px;border-top:1px solid var(--line);text-align:left;vertical-align:middle}.schedule-table th{background:rgba(19,41,56,.86);color:#d9ecf6;font-size:10px;font-weight:800}.schedule-table td{font-size:11px}.schedule-table tr{height:24px}.schedule-table tr.active{background:rgba(37,105,151,.32)}.schedule-table tr.selected{background:rgba(0,122,255,.14);box-shadow:inset 0 0 0 1px var(--blue)}.check-col{width:30px}.time-col{width:56px;min-width:56px;max-width:56px;text-align:left;white-space:nowrap}.schedule-table .metric,.schedule-table .mode-pill{white-space:nowrap}.schedule-table col.col-check{width:30px}.schedule-table col.col-time{width:58px}.schedule-table col.col-mode{width:118px}.schedule-table col.col-power{width:76px}.schedule-table col.col-current{width:78px}.schedule-table col.col-grid{width:54px}.schedule-table col.col-grid-current{width:72px}.schedule-table col.col-soc{width:56px}.schedule-table col.col-price{width:70px}.schedule-table col.col-active{width:56px}.schedule-table col.col-action{width:42px}.slot-check{display:inline-flex;align-items:center;justify-content:center}.slot-check input{display:none}.slot-check span{width:18px;height:18px;border:1px solid rgba(159,190,207,.55);border-radius:5px;background:rgba(255,255,255,.02)}.slot-check input:checked+span{background:var(--blue);border-color:var(--blue);box-shadow:inset 0 0 0 3px rgba(0,0,0,.18)}.slot-check input:checked+span::after{content:"";display:block;width:8px;height:5px;border-left:2px solid #00131f;border-bottom:2px solid #00131f;transform:rotate(-45deg);margin:5px 0 0 5px}
          .mode-pill{display:inline-flex;align-items:center;border-radius:6px;padding:3px 7px;font-weight:800;background:#223241;color:#d7e7ef;white-space:nowrap}.mode-pill.selling{background:rgba(72,154,38,.24);color:var(--green)}.mode-pill.zero{background:rgba(21,155,255,.18);color:#55baff}.mode-pill.ct{background:rgba(188,99,255,.18);color:#ce8cff}.mode-pill.charge{background:rgba(246,166,25,.18);color:#ffc65a}.mode-pill.disabled{background:rgba(142,160,172,.16);color:#d6e1e8}.mode-pill.normal{background:rgba(77,171,247,.18);color:#4dabf7}
          .metric{white-space:nowrap}.metric svg{width:16px;height:16px;vertical-align:-3px}.metric.sell{color:#8cef3b}.metric.discharge{color:#ff4848}.metric.charge{color:#20a9ff}.metric.grid,.metric.grid-current{color:#ffc65a}.metric.soc{color:#d279ff}.metric.price-limit{color:#2dff95}
          .pill{border:0;border-radius:999px;min-width:42px;padding:3px 9px;font-weight:900;cursor:pointer;background:#233849;color:#d9edf5}.pill.on{background:linear-gradient(90deg,#0a68d7,#159bff);color:#fff}.pill.off{background:#263e51;color:#d9edf5}.pill.missing{opacity:.62}
          .schedule-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--line);padding:7px 12px}.schedule-foot strong{color:#2ea7ff}.foot-actions{display:flex;gap:9px;flex-wrap:wrap}.foot-actions button{border:1px solid rgba(100,145,170,.42);border-radius:8px;background:rgba(7,17,27,.72);color:#eaf7ff;min-height:32px;padding:0 12px;display:inline-flex;align-items:center;gap:8px;cursor:pointer}.foot-actions .primary{background:linear-gradient(180deg,#0b7eee,#075bc0);border-color:#159bff}
          .bulk-panel{border:1px solid rgba(107,157,182,.28);border-radius:8px;background:linear-gradient(180deg,rgba(10,29,45,.95),rgba(7,21,33,.96));padding:20px}.bulk-panel h3{margin:0 0 16px;font-size:20px}.range-box{border:1px solid rgba(21,155,255,.35);border-radius:8px;background:rgba(0,81,145,.18);padding:14px;margin-bottom:16px;color:#2ea7ff}.range-box span,.range-box small{display:block;margin-top:5px}.apply-row{display:grid;grid-template-columns:24px 1fr 1.25fr;gap:10px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}.apply-row input[type="checkbox"]{width:20px;height:20px;accent-color:var(--blue)}.preview-box{margin-top:12px;border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,.03);padding:12px;color:#cbdce5}.bulk-actions{display:flex;justify-content:space-between;gap:10px;margin-top:16px}.bulk-actions .primary{background:linear-gradient(180deg,#72d13b,#41a91d);border-color:#75e247;color:#041007}
          input,select{width:100%;min-width:0;box-sizing:border-box;background:rgba(8,22,34,.95);color:#f6fbff;border:1px solid rgba(107,157,182,.34);border-radius:7px;padding:8px}option,select option{background:#fff!important;color:#111!important}.field{position:relative;display:block}.field input{padding-right:42px}.field span{position:absolute;right:10px;top:50%;transform:translateY(-50%);font-weight:800;color:#d8ecf7}.row{min-height:38px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 12px;border-top:1px solid var(--line)}.row strong{text-align:right}.settings-row{min-height:40px;display:grid;grid-template-columns:1fr 260px;gap:12px;align-items:center;padding:9px 12px;border-top:1px solid var(--line)}.settings-row>input[type="checkbox"]{justify-self:end;width:20px;height:20px;accent-color:var(--blue)}.settings-row select,.settings-row .compact-field{max-width:260px;justify-self:end}.tou-editor-field{grid-template-columns:minmax(150px,1fr) minmax(180px,260px)}.tou-field-state{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:8px 18px;margin:0}.tou-reverse-sync{display:grid;gap:5px}.hint{padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,.03);color:#c7d9e2;margin-bottom:12px}.wide-action{width:100%;min-height:38px;border:1px solid rgba(100,145,170,.45);border-radius:8px;background:#173a57;color:#fff;font-weight:800;cursor:pointer}.wide-action:disabled{opacity:.45;cursor:not-allowed}.settings-table{width:100%;border-collapse:collapse}.settings-table th,.settings-table td{padding:8px;border-top:1px solid var(--line);text-align:left}.settings-tabs{display:flex;gap:8px;padding:10px;border-bottom:1px solid var(--line);overflow-x:auto}.settings-tabs button{border:1px solid var(--line2);border-radius:7px;background:rgba(255,255,255,.03);color:#dfeef6;padding:8px 10px;white-space:nowrap}.settings-tabs button.active{border-color:var(--blue);color:#fff;background:rgba(21,155,255,.22)}.overlay{position:fixed;inset:0;background:rgba(0,0,0,.68);display:flex;align-items:center;justify-content:center;z-index:20;padding:16px}.dialog{width:min(760px,100%);max-height:92vh;overflow:auto;border:1px solid rgba(107,157,182,.45);border-radius:12px;background:radial-gradient(circle at 16% 0%,rgba(22,91,139,.2),transparent 36%),linear-gradient(180deg,#071b2a,#061420);box-shadow:0 25px 70px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.04)}.settings-dialog{width:min(880px,100%)}.dialog-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;background:linear-gradient(180deg,rgba(14,50,70,.9),rgba(10,30,44,.86));border-bottom:1px solid rgba(107,157,182,.28)}.dialog-head strong{font-size:19px}.dialog-head button{border:0;background:transparent;color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center}.dialog-head button svg{pointer-events:none}.dialog-body{padding:14px}.dialog-actions{display:flex;justify-content:flex-end;gap:10px;padding:0 14px 14px}.dialog-actions button{border:1px solid var(--line2);border-radius:8px;background:#173a57;color:#fff;min-height:38px;padding:0 16px}.dialog-actions button:disabled{opacity:.45;cursor:not-allowed}.ai-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ai-card{border:1px solid var(--line);border-radius:9px;background:rgba(255,255,255,.03);padding:12px}.ai-card h3{margin:0 0 8px;color:#7ee22d}.ai-proposal,.ai-history{grid-column:1/-1}.ai-proposal-scroll,.ai-history-scroll{overflow:auto;max-height:300px;margin-bottom:10px}.ai-proposal .mini-table,.ai-history .mini-table{min-width:620px}
           .history-toolbar{display:grid;grid-template-columns:repeat(3,minmax(130px,1fr)) repeat(3,auto);gap:8px;align-items:end;margin-bottom:12px}.history-toolbar label{display:grid;gap:4px;color:#a9c1d0;font-size:11px}.history-toolbar button,.danger-action{min-height:38px;border:1px solid var(--line2);border-radius:7px;background:#173a57;color:#fff;padding:0 12px;cursor:pointer}.history-section{border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,.025);margin-bottom:12px;overflow:hidden}.history-section h3{margin:0;padding:10px 12px;color:var(--green);background:rgba(18,42,59,.74)}.history-scroll{max-height:270px;overflow:auto;overscroll-behavior:contain}.history-scroll .settings-table{min-width:780px}.history-scroll details summary{cursor:pointer;color:var(--blue)}.history-scroll pre{max-width:520px;max-height:220px;overflow:auto;white-space:pre-wrap;color:#cfe1ea}.history-rating{display:inline-flex;gap:3px;margin-top:4px}.history-rating button{width:25px;height:24px;border:1px solid var(--line2);border-radius:5px;background:rgba(255,255,255,.03);color:#b9ced9;cursor:pointer}.history-rating button.active{background:var(--green);color:#041007;border-color:var(--green)}.danger-action{background:rgba(138,24,42,.28);border-color:rgba(255,77,99,.55);color:#ff9cab}
           .analysis-history-scroll{overflow-x:hidden}.history-scroll .analysis-history-table{width:100%;min-width:0;table-layout:fixed}.analysis-history-table th,.analysis-history-table td{overflow-wrap:anywhere}.analysis-history-table th:nth-child(1){width:19%}.analysis-history-table th:nth-child(2){width:14%}.analysis-history-table th:nth-child(3){width:20%}.analysis-history-table th:nth-child(4){width:32%}.analysis-history-table th:nth-child(5){width:15%}.analysis-detail-row td{padding:0 10px 8px!important;background:rgba(3,14,23,.45)}.analysis-record{width:100%}.analysis-record summary{padding:8px 2px;font-weight:800;cursor:pointer;color:var(--blue)}.analysis-details{display:grid;gap:10px;padding:2px 0 10px}.analysis-detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.analysis-detail-grid>div,.analysis-price-groups section,.analysis-explanation{border:1px solid var(--line);border-radius:7px;background:rgba(255,255,255,.025);padding:9px}.analysis-detail-grid span,.analysis-explanation span{display:block;margin-bottom:4px;color:#9db7c6;font-size:10px}.analysis-detail-grid strong,.analysis-explanation strong{display:block;overflow-wrap:anywhere}.analysis-price-groups{display:grid;grid-template-columns:1fr 1fr;gap:8px}.analysis-price-groups h4{margin:0 0 6px;color:var(--green)}.analysis-price-groups ul{list-style:none;margin:0;padding:0}.analysis-price-groups li{display:flex;justify-content:space-between;gap:8px;padding:5px 0;border-top:1px solid var(--line)}
           .settings-dialog{width:min(1180px,96vw)!important;height:min(820px,92vh);max-height:92vh!important;overflow:hidden!important;display:grid;grid-template-rows:auto minmax(0,1fr)}.settings-layout{min-height:0;display:grid;grid-template-columns:220px minmax(0,1fr)}.settings-nav{padding:12px;border-right:1px solid var(--line);background:rgba(4,15,24,.58);display:flex;flex-direction:column;gap:7px;overflow-y:auto}.settings-nav button{width:100%;min-height:42px;border:1px solid var(--line2);border-radius:7px;background:rgba(255,255,255,.025);color:#dfeef6;padding:8px 10px;text-align:left;cursor:pointer}.settings-nav button.active{border-color:var(--blue);color:#fff;background:rgba(21,155,255,.22)}.settings-content{min-width:0;overflow:auto;overscroll-behavior:contain;padding:14px}.diagnostic-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-bottom:12px}.diagnostic-summary>div{border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,.03);padding:11px}.diagnostic-summary span{display:block;color:#9db7c6;font-size:11px}.diagnostic-summary strong{display:block;margin-top:5px;overflow-wrap:anywhere}.diagnostic-section{border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:12px;background:rgba(255,255,255,.025)}.diagnostic-section h3{margin:0;padding:10px 12px;background:rgba(18,42,59,.78);color:#dff4ff}.diagnostic-entities{max-height:260px;overflow:auto}.diag-badge{display:inline-flex;border-radius:999px;padding:3px 9px;font-weight:800}.diag-badge.ok{color:var(--green);background:rgba(53,214,111,.12)}.diag-badge.error{color:#ff8b98;background:rgba(255,77,99,.13)}.diagnostic-actions{display:flex;flex-wrap:wrap;gap:8px;padding:12px}.diagnostic-actions button{min-height:38px;border:1px solid var(--line2);border-radius:7px;background:#173a57;color:#fff;padding:0 13px;cursor:pointer}.diagnostic-actions button.danger{background:rgba(138,24,42,.28);border-color:rgba(255,77,99,.55);color:#ff9cab}.diagnostic-actions button.resume{background:rgba(38,112,64,.55);border-color:rgba(103,229,100,.65)}.tou-diagnostics{padding:12px;display:flex;gap:10px;align-items:center;overflow-wrap:anywhere}.schedule-attempt{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;padding:12px}.schedule-attempt>div{border:1px solid var(--line);border-radius:7px;padding:9px;overflow-wrap:anywhere}.schedule-attempt .schedule-attempt-message{grid-column:span 3}.schedule-attempt span{display:block;font-size:11px;color:#9db7c6}.schedule-attempt strong{display:block;margin-top:4px}.schedule-attempt ul{margin:6px 0 0;padding:0;list-style:none}.schedule-attempt li{display:flex;justify-content:space-between;gap:8px;font-size:12px;padding:2px 0}.schedule-attempt.failed{background:rgba(145,28,48,.08)}
           .sales-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:10px}.sales-chart{height:130px;display:grid;grid-template-columns:repeat(24,1fr);gap:4px;align-items:end;padding:10px;border-top:1px solid var(--line)}.sales-bar{height:112px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:4px;min-width:0}.sales-bar span{display:block;width:100%;min-height:4px;border-radius:4px 4px 0 0;background:#35d66f}.sales-bar.now span{background:#ffd166}.sales-bar em{font-style:normal;font-size:10px;color:#8aa8b8;writing-mode:vertical-rl;transform:rotate(180deg)}.sales-tables{display:grid;grid-template-columns:1fr .8fr 1fr;gap:10px;padding:0 10px 10px}.section-label{padding:8px 10px;color:#d9f7ff;background:#1b3445;font-size:12px;font-weight:900;text-transform:uppercase}.sales-scroll{max-height:170px;overflow:auto;overscroll-behavior:contain}.mini-table{width:100%;border-collapse:collapse}.mini-table td{padding:5px 8px;border-top:1px solid var(--line);font-size:12px}
          .status-panel,.sales-panel{background:radial-gradient(circle at 12% 0%,rgba(20,85,130,.22),transparent 30%),linear-gradient(180deg,rgba(5,16,26,.99),rgba(7,21,32,.99));border-color:rgba(107,157,182,.3)}
          .status-panel .panel-title,.sales-panel .panel-title{display:flex;align-items:center;gap:9px;padding:13px 15px;background:transparent;border-bottom:1px solid rgba(107,157,182,.25);font-size:21px}.status-panel .panel-title svg,.sales-panel .panel-title svg{width:21px;height:21px;color:var(--blue)}
          .status-panel .status-grid{gap:10px;padding:12px}.status-panel .stat,.sales-summary .stat{position:relative;display:flex;align-items:center;gap:11px;min-height:58px;padding:10px 12px;border:1px solid rgba(107,157,182,.28);border-radius:8px;background:linear-gradient(180deg,rgba(12,31,45,.84),rgba(6,19,29,.88));box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}
          .stat-icon{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex:0 0 auto;background:rgba(21,155,255,.14);color:#55baff}.stat-icon svg{width:19px;height:19px}.stat-copy{min-width:0;flex:1}.status-panel .stat span,.sales-summary .stat span{font-size:11px;color:#8eacbd}.status-panel .stat strong,.sales-summary .stat strong{font-size:16px;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
           .status-mode .stat-icon{color:var(--green);background:rgba(126,226,45,.14)}.status-mode.warn .stat-icon{color:var(--gold);background:rgba(246,166,25,.16)}.status-mode.bad .stat-icon{color:#ff6b7a;background:rgba(255,77,99,.15)}.status-mode.neutral .stat-icon{color:#a9c1d0;background:rgba(155,178,193,.12)}.status-mode.charge .stat-icon{color:var(--gold);background:rgba(246,166,25,.16)}.status-mode.zero .stat-icon{color:var(--blue);background:rgba(21,155,255,.16)}.status-mode.ct .stat-icon{color:var(--purple);background:rgba(188,99,255,.18)}.status-mode.normal .stat-icon{color:#4dabf7;background:rgba(77,171,247,.14)}.status-pv .stat-icon{color:#ffd166;background:rgba(255,209,102,.14)}.status-home .stat-icon{color:#57b9ff}.status-grid .stat-icon{color:#6ec7ff}.status-battery .stat-icon,.status-soc .stat-icon{color:var(--purple);background:rgba(188,99,255,.14)}.status-sold .stat-icon{color:var(--green);background:rgba(53,214,111,.14)}.status-slot .stat-icon{color:var(--gold);background:rgba(246,166,25,.14)}.status-inverter .stat-icon{color:var(--blue);background:rgba(21,155,255,.14)}.status-action .stat-icon{color:#d8ecf7;background:rgba(155,178,193,.1)}
           .decision-strip{margin:0 12px 12px;padding:10px 13px;border:1px solid rgba(107,157,182,.32);border-left:4px solid var(--blue);border-radius:8px;background:rgba(6,20,31,.82);display:flex;align-items:center;gap:10px}.decision-strip svg{width:19px;height:19px;color:var(--blue)}.decision-strip strong{font-size:13px}.decision-strip span{color:#a9c1d0;font-size:12px}.decision-strip.good{border-left-color:var(--green)}.decision-strip.good svg{color:var(--green)}.decision-strip.warn,.decision-strip.charge{border-left-color:var(--gold)}.decision-strip.warn svg,.decision-strip.charge svg{color:var(--gold)}.decision-strip.bad{border-left-color:#ff4d63}.decision-strip.bad svg{color:#ff6b7a}.decision-strip.ct{border-left-color:var(--purple)}.decision-strip.ct svg{color:var(--purple)}.decision-strip.normal{border-left-color:#4dabf7}.decision-strip.normal svg{color:#4dabf7}
                     .sales-panel{width:100%;box-sizing:border-box}.sales-panel>div{padding:0 2px 2px}.sales-summary{gap:10px;padding:12px}.sales-summary .stat{border-left:3px solid rgba(21,155,255,.72)}.sales-summary .stat:nth-child(1){border-left-color:var(--green)}.sales-summary .stat:nth-child(2){border-left-color:#ffd166}.sales-summary .stat:nth-child(3){border-left-color:var(--blue)}.sales-summary .stat:nth-child(4){border-left-color:var(--purple)}.sales-summary .stat:nth-child(5){border-left-color:var(--gold)}
          .sales-chart{height:118px;margin:0 12px 12px;padding:10px 8px 7px;border:1px solid rgba(107,157,182,.25);border-radius:8px;background:rgba(4,15,24,.7)}.sales-bar{height:98px}.sales-bar span{background:linear-gradient(180deg,#74ea4b,#28b963);box-shadow:0 0 10px rgba(53,214,111,.12)}.sales-bar.now span{background:linear-gradient(180deg,#ffe08a,#f5b942)}
          .sales-tables{gap:12px;padding:0 12px 12px}.sales-tables>div{overflow:hidden;border:1px solid rgba(107,157,182,.25);border-radius:8px;background:rgba(4,15,24,.62)}.section-label{padding:9px 11px;background:rgba(18,42,59,.86);color:#d8edf8;font-size:11px;letter-spacing:0;text-transform:uppercase}.mini-table td{padding:6px 9px;border-top:1px solid rgba(118,166,190,.16);font-size:11px}.mini-table tr:hover td{background:rgba(21,155,255,.05)}
           .dialog-head{position:sticky;top:0;z-index:5;background:linear-gradient(180deg,rgba(14,50,70,.98),rgba(10,30,44,.98))}.dialog-actions{position:sticky;bottom:0;z-index:4;padding:12px 14px;background:rgba(6,20,32,.98);border-top:1px solid var(--line)}.ai-dialog{width:min(900px,96vw);height:min(900px,92vh);max-height:92vh;overflow:hidden;display:grid;grid-template-rows:auto minmax(0,1fr)}.ai-dialog>.dialog-body{overflow:auto;overscroll-behavior:contain}.ai-proposal-scroll,.ai-history-scroll{max-height:360px}
           .ai-dialog-v2{width:min(1700px,96vw)!important;height:min(1040px,90vh)!important;grid-template-rows:auto minmax(0,1fr);background:radial-gradient(circle at 18% 5%,rgba(0,117,190,.14),transparent 38%),linear-gradient(150deg,#061a29,#03111d 72%)}.ai-shell{min-height:0;display:grid;grid-template-columns:225px minmax(0,1fr)}.ai-sidebar{min-height:0;border-right:1px solid rgba(96,151,178,.28);background:rgba(3,14,23,.54);display:flex;flex-direction:column;padding:14px 10px}.ai-sidebar nav{display:grid;gap:8px}.ai-sidebar nav button{display:flex;align-items:center;gap:10px;min-height:44px;padding:0 12px;border:1px solid transparent;border-radius:7px;background:transparent;color:#cfe1eb;text-align:left;cursor:pointer}.ai-sidebar nav button span{width:20px;color:#45b8ff;font-size:18px;text-align:center}.ai-sidebar nav button:hover{background:rgba(21,155,255,.08)}.ai-sidebar nav button.active{border-color:#169cf5;background:rgba(21,155,255,.13);color:#fff}.ai-sidebar nav button.active:nth-child(2){border-color:#58bd21;background:rgba(77,180,37,.14)}.ai-sidebar nav button.active:nth-child(2) span{color:#7ee22d}.ai-learning-status{margin-top:auto;padding:13px 9px;border-top:1px solid var(--line);display:grid;gap:4px}.ai-learning-status span,.ai-learning-status small{color:#91adbc;font-size:11px}.ai-learning-status strong{color:#7ee22d;font-size:12px}.ai-main{min-width:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;padding:18px}.ai-main h3{margin:0 0 10px;color:#7ee22d;font-size:17px}.ai-overview-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ai-metric-card,.ai-decision-grid>section,.ai-chart-card{border:1px solid rgba(103,158,184,.28);border-radius:8px;background:linear-gradient(180deg,rgba(14,38,54,.72),rgba(7,25,38,.75));padding:14px}.ai-overview-grid>.ai-chart-card{grid-column:1/-1}.ai-price-columns{display:grid;grid-template-columns:1fr 1fr;gap:12px}.ai-price-columns section{min-width:0;border:1px solid rgba(103,158,184,.18);border-radius:6px;overflow:hidden}.ai-price-columns h4{margin:0;padding:8px 10px;background:rgba(20,56,76,.55);color:#dff3fc}.ai-price-columns table{width:100%;border-collapse:collapse}.ai-price-columns td{padding:6px 10px;border-top:1px solid rgba(103,158,184,.16);font-size:12px}.ai-price-columns td:last-child{text-align:right;font-weight:800}.ai-empty{color:#90aab9;text-align:center;padding:12px}.ai-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.ai-kpis>div{border:1px solid rgba(103,158,184,.2);border-radius:6px;padding:9px;background:rgba(3,16,25,.45)}.ai-kpis span{display:block;color:#93adbc;font-size:10px}.ai-kpis strong{display:block;margin-top:4px;color:#f3fbff}.ai-proposal-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}.ai-day-tabs,.ai-view-tools{display:flex;align-items:center;gap:7px}.ai-day-tabs button,.ai-view-tools button{min-height:36px;padding:0 14px;border:1px solid var(--line2);border-radius:6px;background:#122f45;color:#e2f1f8;cursor:pointer}.ai-day-tabs button.active{background:#4b9d25;border-color:#64ba32;color:#fff}.ai-view-tools button.select{background:#1b77b5;border-color:#37a9f3}.ai-view-tools button.neutral{background:#173043}.ai-view-tools button:disabled{opacity:.42;cursor:not-allowed}.ai-plan-table-wrap{overflow-x:auto;border:1px solid rgba(103,158,184,.28);border-radius:8px}.ai-plan-table{width:100%;min-width:940px;border-collapse:collapse}.ai-plan-table th{position:sticky;top:0;z-index:2;padding:9px 8px;background:#0b283a;color:#d9ecf5;font-size:11px}.ai-plan-table td{padding:8px;border-top:1px solid rgba(103,158,184,.17);font-size:11px;white-space:nowrap}.ai-plan-table tr.proposed{background:rgba(32,91,46,.05)}.ai-plan-table tr.unchanged{opacity:.62}.ai-plan-table input{width:17px;height:17px;accent-color:#6ccc33}.ai-confidence{display:inline-flex;min-width:43px;justify-content:center;border-radius:999px;padding:3px 7px;font-weight:900}.ai-confidence.good{color:#7ee22d;background:rgba(126,226,45,.12)}.ai-confidence.warn{color:#ffd166;background:rgba(255,209,102,.12)}.ai-confidence.bad{color:#ff7585;background:rgba(255,77,99,.14)}.ai-decision-grid{display:grid;grid-template-columns:1fr 1.25fr 1.35fr;gap:10px;margin:12px 0}.ai-decision-grid>section{min-height:116px}.ai-decision-grid p{line-height:1.45;color:#d3e5ed}.ai-variants{display:grid;gap:5px}.ai-variants button{display:flex;justify-content:space-between;gap:8px;border:0;background:transparent;color:#d6e7ee;text-align:left;padding:3px}.ai-variants button.active strong{color:#7ee22d}.ai-variants span{color:#94adba;font-size:10px}.ai-chart-card{margin-top:12px;overflow:hidden}.ai-chart-legend{display:flex;flex-wrap:wrap;gap:14px;justify-content:center;color:#a9c0cc;font-size:11px}.ai-chart-legend span:before{content:"";display:inline-block;width:11px;height:7px;margin-right:5px;border-radius:2px;background:#7d96a3}.ai-chart-legend .load:before{background:#32a8e8}.ai-chart-legend .pv:before{background:#67bd2e}.ai-chart-legend .soc:before{background:#ffd200}.ai-chart-legend .sell:before{background:#7ee22d;border-radius:50%}.ai-chart-legend .charge:before{background:#ffd166;border-radius:50%}.ai-chart-card svg{display:block;width:100%;height:auto;max-height:270px}.ai-support-grid{display:grid;grid-template-columns:.8fr 1.7fr;gap:10px;margin-top:10px}.ai-weather-main{display:flex;align-items:center;gap:12px}.ai-weather-main svg{width:46px;height:46px;color:#ffd166}.ai-weather-main strong{font-size:27px}.ai-weather small{color:#93adbc}.ai-quality-card ul{list-style:none;margin:0;padding:0}.ai-quality-card li{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-top:1px solid rgba(103,158,184,.15)}.ai-quality-card li span{color:#91aeba}.ai-quality-card li strong{text-align:right}.ai-apply-plan{position:sticky;bottom:-18px;z-index:4;width:100%;min-height:44px;margin:14px 0 -18px;border:1px solid #4e9e28;border-radius:7px;background:linear-gradient(180deg,#37871d,#276414);color:#fff;font-weight:900;cursor:pointer;box-shadow:0 -9px 22px rgba(3,15,24,.8)}.ai-apply-plan:disabled{opacity:.4;cursor:not-allowed}.ai-day-plan>.ai-kpis{grid-template-columns:repeat(5,minmax(0,1fr))}.ai-quality-full{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}
           .ai-cancel-plan{min-height:34px;border:1px solid rgba(255,95,112,.5);border-radius:6px;background:rgba(120,24,39,.28);color:#ffabb5;padding:0 11px;cursor:pointer}
           .ai-chart-legend .tariff:before{background:rgba(255,209,102,.45)}
           .ai-chart-v2{position:relative;overflow:visible}.ai-chart-v2 h3{margin-bottom:8px}.ai-chart-scroll{overflow-x:auto;overflow-y:hidden;scrollbar-color:#527385 #071924}.ai-chart-v2 svg{width:100%;min-width:790px;max-height:none}.ai-chart-grid{stroke:rgba(152,195,216,.17);stroke-width:1}.ai-chart-baseline{stroke:#88a9b9;stroke-width:1.5}.ai-chart-axis,.ai-day-label,.ai-now-label{fill:#9ab7c6;font-size:11px}.ai-day-label{fill:#d7edf7;font-weight:800}.ai-bar-load{fill:#35aee8}.ai-bar-actual{fill:#ff9f43}.ai-bar-solcast{fill:#77d84b;opacity:.72}.ai-forecast-band{fill:rgba(255,209,102,.14);stroke:rgba(255,209,102,.3);stroke-width:1}.ai-line-corrected{fill:none;stroke:#b77cff;stroke-width:3;stroke-linejoin:round;stroke-linecap:round}.ai-line-soc{fill:none;stroke:#ffd200;stroke-width:3;stroke-linejoin:round;stroke-linecap:round}.ai-min-soc{stroke:#ff7585;stroke-width:1.3;stroke-dasharray:6 5}.ai-action-sell{fill:#7ee22d}.ai-action-charge{fill:#ffd166}.ai-cheap-zone{fill:rgba(255,209,102,.07)}.ai-chart-weather{font-size:15px}.ai-day-separator{stroke:#5cc2ff;stroke-width:2;stroke-dasharray:6 5}.ai-now-line{stroke:#ff5f70;stroke-width:2;stroke-dasharray:5 4}.ai-now-label{fill:#ff9aa5;font-weight:800}.ai-chart-hit{fill:transparent;pointer-events:all;cursor:crosshair}.ai-chart-crosshair-x,.ai-chart-crosshair-y{display:none;stroke:#d8f2ff;stroke-width:1;stroke-dasharray:4 3;pointer-events:none}.ai-chart-crosshair-x.visible,.ai-chart-crosshair-y.visible{display:block}.ai-chart-tooltip{display:none;position:absolute;z-index:20;width:min(286px,calc(100% - 16px));padding:11px;border:1px solid #4d7b94;border-radius:7px;background:rgba(3,16,25,.97);box-shadow:0 12px 30px rgba(0,0,0,.45);color:#e9f6fb;font-size:11px;pointer-events:none}.ai-chart-tooltip.visible{display:block}.ai-chart-tooltip>strong{display:block;margin-bottom:8px;color:#7ee22d;font-size:12px}.ai-chart-tooltip>div{display:grid;grid-template-columns:1fr auto;gap:4px 10px}.ai-chart-tooltip span{color:#91adbc}.ai-chart-tooltip b{text-align:right}.ai-chart-tip-source{display:none}.ai-chart-help{display:block;margin-top:5px;color:#83a3b3}.ai-chart-legend .actual:before{background:#ff9f43}.ai-chart-legend .solcast:before{background:#77d84b}.ai-chart-legend .corrected:before{height:3px;background:#b77cff}.ai-chart-legend .band:before{background:rgba(255,209,102,.35);border:1px solid rgba(255,209,102,.6)}
           .ai-weather-v2{min-width:0}.ai-weather-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.ai-weather-head>div:first-child{display:flex;align-items:center;gap:12px}.ai-weather-icon{font-size:42px;line-height:1}.ai-weather-head h3{margin:0!important;text-transform:none}.ai-weather-temperature{text-align:right}.ai-weather-temperature strong{display:block;color:#f3fbff;font-size:26px}.ai-weather-temperature span{color:#9db7c5}.ai-weather-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:12px 0}.ai-weather-facts span{padding:8px;border:1px solid rgba(103,158,184,.18);border-radius:6px;color:#91adbc}.ai-weather-facts b{display:block;margin-top:3px;color:#e6f4fa}.ai-weather-tabs{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid rgba(103,158,184,.25)}.ai-weather-tabs button{padding:9px;border:0;border-bottom:2px solid transparent;background:transparent;color:#b7cfda;cursor:pointer}.ai-weather-tabs button.active{border-bottom-color:#2aaaff;color:#52baff}.ai-weather-strip{display:flex;gap:7px;overflow-x:auto;padding:10px 0}.ai-weather-day,.ai-weather-hour{min-width:66px;display:grid;justify-items:center;gap:3px;padding:7px;border-radius:6px;background:rgba(3,16,25,.42)}.ai-weather-day span,.ai-weather-hour span{font-size:25px}.ai-weather-day small,.ai-weather-hour small{color:#92aebb}.ai-weather-source{display:block;margin-top:3px}.ai-energy-48>.ai-support-grid{grid-template-columns:1fr 1fr}
           .ai-proposals-view>h2{margin:0 0 14px;color:#7ee22d;font-size:18px}.ai-proposal-explainer{display:grid;grid-template-columns:auto minmax(0,1fr);gap:5px 12px;margin:0 0 12px;padding:11px 13px;border:1px solid rgba(126,226,45,.32);border-radius:8px;background:rgba(56,128,29,.09);color:#cfe2eb}.ai-proposal-explainer strong{grid-row:1/3;color:#7ee22d}.ai-proposal-explainer span{line-height:1.4}.ai-plan-table td strong,.ai-plan-table td small{display:block}.ai-plan-table td small{margin-top:2px;color:#91adbc;font-size:9px}
           .ai-readable-chart{position:relative;overflow:visible;padding:15px 12px 12px;background:radial-gradient(circle at 45% 15%,rgba(17,84,117,.13),transparent 45%),linear-gradient(180deg,rgba(9,35,51,.88),rgba(5,23,35,.92))}.ai-readable-chart h3{margin:0 0 10px;color:#7ee22d}.ai-readable-chart .ai-chart-scroll{border-top:1px solid rgba(111,166,191,.13);overflow-x:auto;overflow-y:hidden;scrollbar-color:#527385 #071924;scrollbar-width:thin}.ai-readable-chart svg{display:block;width:100%;height:auto;max-height:none!important}.ai-readable-legend{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 13px;padding:0 5px 10px}.ai-readable-legend button{display:inline-flex;align-items:center;gap:6px;border:0;background:transparent;color:#adc5d1;font:inherit;font-size:11px;cursor:pointer;padding:4px 5px;border-radius:4px}.ai-readable-legend button:hover{background:rgba(89,164,201,.1);color:#e9f7fd}.ai-readable-legend button.disabled{opacity:.3;text-decoration:line-through}.ai-readable-legend i{display:block;width:14px;height:7px;border-radius:2px;background:#7b96a4}.ai-readable-legend .load i{background:#35aee8}.ai-readable-legend .actual i{background:#ff8a32}.ai-readable-legend .solcast i{height:3px;background:#67c842}.ai-readable-legend .corrected i{height:3px;background:#bd6dff}.ai-readable-legend .band i{height:9px;background:rgba(151,191,213,.34);border:1px solid rgba(161,205,228,.55)}.ai-readable-legend .soc i{height:3px;background:#ffd200}.ai-readable-legend .minimum i{height:2px;background:repeating-linear-gradient(90deg,#ff6577 0 5px,transparent 5px 8px)}
           .ai-readable-grid{stroke:rgba(136,184,205,.16);stroke-width:1}.ai-readable-grid-v{stroke-dasharray:3 4;stroke:rgba(139,187,207,.24)}.ai-readable-baseline{stroke:#66899b;stroke-width:1.2}.ai-readable-axis,.ai-readable-hour,.ai-readable-unit,.ai-readable-section-label,.ai-readable-day-label{fill:#a7c1ce;font-size:11px}.ai-readable-unit{fill:#dcecf4;font-weight:800;font-size:12px}.ai-readable-hour{fill:#c6dce6;font-weight:700}.ai-readable-load{fill:#35aee8;filter:drop-shadow(0 0 2px rgba(53,174,232,.25))}.ai-readable-actual{fill:#ff8a32;filter:drop-shadow(0 0 2px rgba(255,138,50,.25))}.ai-readable-band{fill:rgba(151,191,213,.2);stroke:rgba(165,204,224,.3);stroke-width:1}.ai-readable-solcast{fill:none;stroke:#67c842;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}.ai-readable-corrected{fill:none;stroke:#bd6dff;stroke-width:2.8;stroke-linecap:round;stroke-linejoin:round}.ai-readable-soc{fill:none;stroke:#ffd200;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.ai-readable-min-soc{stroke:#ff6577;stroke-width:1.6;stroke-dasharray:7 6}.ai-readable-min-label{fill:#ff8996;font-size:10px;font-weight:700}.ai-readable-weather{font-size:18px}.ai-weather-risk{opacity:.9}.ai-weather-risk.low{fill:#65c95a}.ai-weather-risk.medium{fill:#ffd166}.ai-weather-risk.high{fill:#49aaff}.ai-weather-risk.missing{fill:#536d79;opacity:.35}.ai-readable-section-label{font-weight:800;fill:#9fb9c6}.ai-status-grid{stroke:rgba(116,166,188,.16);stroke-width:1}.ai-status-grid-v{stroke-dasharray:3 4}.ai-status-label{font-size:10px;font-weight:700}.ai-status-label.sell{fill:#7ee22d}.ai-status-label.charge{fill:#ffd200}.ai-status-label.tariff{fill:#b39a50}.ai-status-sell{fill:#69d438;stroke:#8de960;stroke-width:1}.ai-status-charge{fill:#ffd200;stroke:#ffe36a;stroke-width:1}.ai-status-tariff{fill:#9f863d;stroke:#c7ad5b;stroke-width:1}.ai-readable-day-separator{stroke:#52bfff;stroke-width:2.2;stroke-dasharray:7 5}.ai-readable-day-label{fill:#d8eff9;font-size:12px;font-weight:900}.ai-readable-now{stroke:#ff5d70;stroke-width:2;stroke-dasharray:6 4}.ai-readable-now-tag{fill:#f3f7f9;stroke:#ff5d70}.ai-readable-now-text{fill:#172d38;font-size:10px;font-weight:900}.ai-readable-chart .ai-chart-help{margin:8px 2px 0}.ai-readable-chart .ai-chart-tooltip{width:min(300px,calc(100% - 16px))}
           .ai-energy-48-crisp{grid-column:1/-1;min-width:0}.ai-energy-48-crisp>h3{margin:0 0 10px;color:#7ee22d}.ai-readable-stack{display:grid;gap:12px}.ai-crisp-chart{position:relative;overflow:visible;padding:15px 14px 12px;background:radial-gradient(circle at 50% 0%,rgba(18,86,117,.12),transparent 46%),linear-gradient(180deg,rgba(9,34,49,.92),rgba(5,22,33,.94))}.ai-crisp-chart h3{margin:0 0 9px;color:#7ee22d;font-size:16px}.ai-crisp-legend{display:flex;justify-content:center;flex-wrap:wrap;gap:4px 8px;margin:0 0 10px;padding:6px 8px;border:1px solid rgba(103,158,184,.22);border-radius:7px;background:rgba(3,14,23,.38)}.ai-crisp-legend button{display:inline-flex;align-items:center;gap:4px;border:1px solid rgba(103,158,184,.18);border-radius:5px;background:rgba(255,255,255,.04);color:#b8cdd7;font:inherit;font-size:10px;padding:3px 6px;cursor:pointer}.ai-crisp-legend button:hover{background:rgba(69,149,188,.12);color:#fff}.ai-crisp-legend button.disabled{opacity:.32;text-decoration:line-through}.ai-crisp-legend i{display:block;width:13px;height:7px;border-radius:2px;background:#35aee8}.ai-crisp-legend .actual i{background:#ff8a32}.ai-crisp-legend .solcast i,.ai-crisp-legend .corrected i,.ai-crisp-legend .soc i,.ai-crisp-legend .minimum i{height:3px}.ai-crisp-legend .solcast i{background:#67c842}.ai-crisp-legend .corrected i{background:#bd6dff}.ai-crisp-legend .band i{height:9px;background:rgba(151,191,213,.34);border:1px solid rgba(161,205,228,.55)}.ai-crisp-legend .soc i{background:#ffd200}.ai-crisp-legend .minimum i{background:repeating-linear-gradient(90deg,#ff6577 0 5px,transparent 5px 8px)}.ai-crisp-layout{display:grid;grid-template-columns:44px minmax(0,1fr) 38px;gap:7px;align-items:stretch}.ai-crisp-main{min-width:0}.ai-crisp-plot{position:relative;height:268px;border-bottom:1px solid rgba(119,166,188,.3);background:linear-gradient(180deg,rgba(4,18,28,.25),rgba(4,18,28,.52))}.ai-crisp-svg{display:block!important;width:100%!important;min-width:0!important;height:100%!important;max-height:none!important;overflow:visible}.ai-crisp-grid{stroke:rgba(118,164,185,.18);stroke-width:1}.ai-crisp-guide{stroke:rgba(123,170,191,.2);stroke-width:1;stroke-dasharray:5 6}.ai-crisp-baseline{stroke:rgba(157,202,222,.58);stroke-width:1}.ai-crisp-load{fill:#35aee8}.ai-crisp-actual{fill:#ff8a32}.ai-crisp-band{fill:rgba(151,191,213,.18);stroke:rgba(171,210,228,.38);stroke-width:1}.ai-crisp-solcast{fill:none;stroke:#67c842;stroke-width:2.6;stroke-linejoin:round;stroke-linecap:round}.ai-crisp-corrected{fill:none;stroke:#bd6dff;stroke-width:2.7;stroke-linejoin:round;stroke-linecap:round}.ai-crisp-soc{fill:none;stroke:#ffd200;stroke-width:2.8;stroke-linejoin:round;stroke-linecap:round}.ai-crisp-min-soc{stroke:#ff6577;stroke-width:1.5;stroke-dasharray:7 5}.ai-crisp-now{stroke:#ff5d70;stroke-width:1.8;stroke-dasharray:6 4}.ai-crisp-now-tag{position:absolute;top:7px;right:8px;border:1px solid #ff5d70;border-radius:4px;background:#f4f7f8;color:#263943;padding:2px 6px;font-size:10px;font-weight:900}.ai-crisp-hit{stroke:none!important;stroke-width:0!important;fill:transparent!important}.ai-crisp-axis{display:flex;flex-direction:column;justify-content:space-between;min-height:268px;color:#a9c3d0;font-size:11px;font-weight:700}.ai-crisp-axis b{color:#e3f2f7;font-size:12px}.ai-crisp-axis-left{align-items:flex-end;text-align:right}.ai-crisp-axis-right{align-items:flex-start;text-align:left}.ai-crisp-time-grid,.ai-crisp-weather-grid{display:grid;grid-template-columns:repeat(24,minmax(0,1fr));margin-left:0}.ai-crisp-time-grid{min-height:25px;align-items:start;padding-top:6px;color:#c6dbe5;font-size:10px;font-weight:800}.ai-crisp-time-grid span{text-align:center;white-space:nowrap}.ai-crisp-weather-grid{min-height:31px;border-top:1px solid rgba(104,151,174,.12);align-items:center}.ai-crisp-weather-cell{position:relative;display:flex;align-items:center;justify-content:center;min-width:0;height:30px;cursor:default}.ai-crisp-weather-cell b{font-size:18px;line-height:1;font-weight:400}.ai-crisp-weather-cell i{position:absolute;bottom:2px;width:13px;height:2px;border-radius:4px;background:#536d79;opacity:.35}.ai-crisp-weather-cell i.low{background:#65c95a;opacity:.9}.ai-crisp-weather-cell i.medium{background:#ffd166;opacity:.9}.ai-crisp-weather-cell i.high{background:#49aaff;opacity:.9}.ai-crisp-status{display:grid;grid-template-columns:74px minmax(0,1fr);align-items:center;gap:3px 8px;margin-top:4px;padding-top:5px;border-top:1px solid rgba(104,151,174,.18);font-size:10px}.ai-crisp-status>span{font-weight:800;color:#92afbd}.ai-crisp-status>div{display:grid;grid-template-columns:repeat(24,minmax(0,1fr));gap:2px;height:13px}.ai-crisp-status>div span{display:block;border-radius:3px;background:rgba(102,137,153,.12)}.ai-crisp-status>div span.active.sell{background:#69d438;box-shadow:0 0 0 1px rgba(141,233,96,.55) inset}.ai-crisp-status>div span.active.charge{background:#ffd200;box-shadow:0 0 0 1px rgba(255,227,106,.55) inset}.ai-crisp-status>div span.active.tariff{background:#9f863d;box-shadow:0 0 0 1px rgba(199,173,91,.55) inset}.ai-crisp-chart .ai-chart-tooltip{width:min(300px,calc(100% - 18px))}.ai-crisp-chart .ai-chart-help{margin:8px 1px 0}.ai-energy-48-crisp .ai-crisp-chart{margin-top:0}
           .ai-overview-grid>.ai-wide-card{grid-column:1/-1}.ai-sale-rankings,.ai-profile-cards{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}.ai-sale-profile{min-width:0;border:1px solid rgba(103,158,184,.25);border-radius:8px;background:rgba(3,17,27,.38);padding:11px}.ai-sale-profile.disabled{opacity:.82}.ai-sale-profile header{display:grid;gap:8px;margin-bottom:9px}.ai-sale-profile header h4{margin:0;color:#7ee22d}.ai-sale-profile header strong{color:#b9d0dc;font-size:11px}.ai-profile-parameters,.ai-tariff-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ai-profile-parameters span,.ai-tariff-summary span{min-width:0;border:1px solid rgba(103,158,184,.16);border-radius:5px;padding:6px;color:#91adbc;font-size:10px;overflow-wrap:anywhere}.ai-profile-parameters b,.ai-tariff-summary b{display:block;margin-top:3px;color:#e6f5fa}.ai-rank-day h5{margin:0;padding:7px 9px;background:rgba(20,56,76,.55);color:#dff3fc}.ai-rank-row{border-top:1px solid rgba(103,158,184,.16)}.ai-rank-row summary{display:grid;grid-template-columns:minmax(90px,.8fr) minmax(110px,max-content) minmax(150px,1.4fr);gap:8px;align-items:center;padding:8px;cursor:pointer;font-size:11px}.ai-rank-row summary>*{min-width:0}.ai-rank-row summary strong{color:#fff;text-align:right;white-space:nowrap}.ai-rank-row summary em{color:#90aeba;text-align:right;font-style:normal;white-space:normal;overflow-wrap:anywhere}.ai-rank-row.recommended summary em{color:#7ee22d}.ai-rank-row>div{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;padding:0 9px 9px;color:#a9c1cd;font-size:10px}.ai-rank-row>div span{overflow-wrap:anywhere}.ai-rank-row>div b{color:#e4f3f8}.ai-warning{border-left:3px solid #ffd166;padding:7px 9px;background:rgba(255,209,102,.07);color:#ffe3a0}.ai-note{color:#98b2bf}.ai-other-hours{grid-column:1/-1;margin-top:3px;color:#a9c1cd}.ai-other-hours summary{cursor:pointer;color:#d8ebf3}.ai-profile-cards{grid-template-columns:repeat(3,minmax(0,1fr))}.ai-profile-card{min-width:0;border:1px solid rgba(103,158,184,.24);border-radius:7px;padding:10px;background:rgba(4,20,31,.48)}.ai-profile-card.disabled{opacity:.72}.ai-profile-card h4{margin:0 0 8px;color:#7ee22d}.ai-profile-card dl{display:grid;gap:4px;margin:0}.ai-profile-card dl div{display:flex;justify-content:space-between;gap:8px;border-top:1px solid rgba(103,158,184,.13);padding-top:4px}.ai-profile-card dt{color:#91adbc;font-size:10px}.ai-profile-card dd{margin:0;text-align:right;font-size:10px;font-weight:800;overflow-wrap:anywhere}.ai-weather-compact>div{display:flex;justify-content:space-between;gap:9px;padding:6px 0;border-top:1px solid rgba(103,158,184,.15)}.ai-weather-compact span{color:#91adbc}.ai-warnings ul{margin:0;padding-left:20px}.ai-warnings li{margin:5px 0}.ai-plan-group th{position:static!important;text-align:left!important;background:#12384c!important;color:#7ee22d!important;border-top:1px solid #28566c}.ai-plan-group.optional th{color:#a9c1cd!important}.ai-proposals-view{min-height:100%;display:flex;flex-direction:column;padding-bottom:72px}.ai-action-footer{position:sticky;bottom:0;z-index:8;margin:14px -18px -18px;padding:10px 18px max(10px,env(safe-area-inset-bottom));border-top:1px solid rgba(103,158,184,.35);background:#061724}.ai-action-footer .ai-apply-plan{position:static;bottom:auto;margin:0;box-shadow:none}.ai-crisp-effective-min-soc{stroke:#ffad42;stroke-width:1.5;stroke-dasharray:4 4}.ai-crisp-legend .effective-minimum i{height:3px;background:repeating-linear-gradient(90deg,#ffad42 0 4px,transparent 4px 7px)}
           @media(max-width:980px){.ai-energy-48>.ai-support-grid{grid-template-columns:1fr}.ai-chart-v2 svg{min-width:860px}.ai-weather-facts{grid-template-columns:1fr 1fr}.ai-weather-facts span:last-child{grid-column:1/-1}.ai-crisp-chart{padding:12px 9px}.ai-crisp-layout{grid-template-columns:36px minmax(0,1fr) 31px;gap:4px}.ai-crisp-plot{height:236px}.ai-crisp-axis{min-height:236px;font-size:10px}.ai-crisp-legend{justify-content:flex-start;gap:4px 7px}.ai-crisp-legend button{font-size:10px}.ai-crisp-status{grid-template-columns:66px minmax(0,1fr);font-size:9px}.ai-crisp-svg{min-width:0!important}.ai-sale-rankings,.ai-profile-cards{grid-template-columns:minmax(0,1fr)}.ai-action-footer{margin-left:-10px;margin-right:-10px;margin-bottom:-10px;padding-left:10px;padding-right:10px}}
           @media(max-width:1500px){.info-grid{grid-template-columns:1fr 1fr}.info-grid>.panel:nth-child(3){grid-column:1/-1}.schedule-main.selecting{grid-template-columns:1fr}.bulk-panel{max-width:none}.mode-legend{grid-template-columns:repeat(3,minmax(0,1fr))}}
           .ai-settings-pane{min-width:0}.ai-settings-tabs{position:sticky;top:0;z-index:3;background:#071b2a}.ai-days-row{align-items:start}.ai-day-presets{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end}.ai-day-presets button{border:1px solid var(--line2);border-radius:6px;background:#15354d;color:#e5f3f9;padding:6px 8px}.ai-weekdays{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px;padding:8px 12px;border-top:1px solid var(--line)}.ai-weekdays label{display:flex;align-items:center;justify-content:center;gap:4px;border:1px solid var(--line);border-radius:6px;padding:7px 3px;font-size:11px}.ai-weekdays input{width:auto}.ai-note-row textarea{width:100%;min-height:70px;box-sizing:border-box;background:#081622;color:#fff;border:1px solid var(--line2);border-radius:7px;padding:8px;resize:vertical}.ai-profile-summary,.ai-hour-detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0}.ai-profile-summary>div,.ai-hour-detail-grid>div{border:1px solid var(--line);border-radius:7px;padding:9px;background:rgba(4,20,31,.55)}.ai-profile-summary span,.ai-hour-detail-grid span{display:block;color:#91adbc;font-size:10px}.ai-profile-summary strong,.ai-hour-detail-grid strong{display:block;margin-top:4px;overflow-wrap:anywhere}.ai-hour-detail{margin:10px 0;padding:12px;border:1px solid rgba(22,156,245,.5);border-radius:8px;background:rgba(7,37,55,.78)}.ai-hour-detail p{overflow-wrap:anywhere;color:#bcd0dc}.ai-plan-table tr[data-ai-hour-detail]{cursor:pointer}.ai-plan-table tr.selected-detail{outline:1px solid #169cf5;outline-offset:-1px}.ai-profile-impact,.ai-status-list{list-style:none;margin:0;padding:0}.ai-profile-impact li,.ai-status-list li{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-top:1px solid var(--line)}.ai-profile-impact span,.ai-status-list span{color:#91adbc}.ai-profile-impact strong,.ai-status-list strong{text-align:right;overflow-wrap:anywhere}
           @media(max-width:980px){.dem-v073{padding:10px}.info-grid{grid-template-columns:1fr}.status-grid,.sales-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.info-grid>.panel{height:auto;min-height:340px}.schedule-head{display:grid}.schedule-tools{justify-content:stretch}.tool-btn{flex:1}.mode-legend{grid-template-columns:1fr 1fr}.schedule-table{min-width:1160px}.schedule-table-card{overflow-x:auto}.sales-tables{grid-template-columns:1fr}.sales-chart{overflow-x:auto;grid-template-columns:repeat(24,24px)}.price-scroll{height:260px;overflow:auto;scrollbar-gutter:stable}.solcast-days{grid-template-columns:repeat(2,1fr)}.settings-layout{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr)}.settings-nav{flex-direction:row;overflow-x:auto;overflow-y:hidden;border-right:0;border-bottom:1px solid var(--line)}.settings-nav button{width:auto;min-width:max-content;text-align:center}.diagnostic-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.ai-shell{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr)}.ai-sidebar{border-right:0;border-bottom:1px solid var(--line);padding:7px}.ai-sidebar nav{display:flex;overflow-x:auto}.ai-sidebar nav button{min-width:max-content}.ai-learning-status{display:none}.ai-overview-grid{grid-template-columns:1fr}.ai-overview-grid>.ai-chart-card{grid-column:auto}.ai-decision-grid,.ai-quality-full{grid-template-columns:1fr}.ai-support-grid{grid-template-columns:1fr}.ai-day-plan>.ai-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.ai-dialog-v2{width:100%!important;max-width:100%!important;min-width:0!important;box-sizing:border-box;overflow:hidden}.ai-dialog-v2 .ai-shell,.ai-dialog-v2 .ai-sidebar,.ai-dialog-v2 .ai-main,.ai-dialog-v2 .ai-overview-grid,.ai-dialog-v2 .ai-price-columns,.ai-dialog-v2 .ai-kpis,.ai-dialog-v2 .ai-decision-grid,.ai-dialog-v2 .ai-support-grid,.ai-dialog-v2 .ai-quality-full,.ai-dialog-v2 .ai-metric-card,.ai-dialog-v2 .ai-chart-card{width:100%;max-width:100%;min-width:0;box-sizing:border-box}.ai-dialog-v2 .ai-sidebar{overflow:hidden}.ai-dialog-v2 .ai-sidebar nav{display:flex;width:100%;max-width:100%;min-width:0;overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;touch-action:pan-x}.ai-dialog-v2 .ai-sidebar nav button{flex:0 0 auto;min-width:max-content;max-width:none;white-space:nowrap}.ai-dialog-v2 .ai-main{overflow-x:hidden}.ai-dialog-v2 .ai-plan-table-wrap,.ai-dialog-v2 .ai-chart-scroll,.ai-dialog-v2 .ai-weather-strip{width:100%;max-width:100%;min-width:0;box-sizing:border-box;overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain}.ai-dialog-v2 .ai-crisp-chart,.ai-dialog-v2 .ai-crisp-layout,.ai-dialog-v2 .ai-crisp-main,.ai-dialog-v2 .ai-crisp-plot{width:100%;max-width:100%;min-width:0;box-sizing:border-box}.ai-dialog-v2 .ai-crisp-chart{overflow:hidden}.ai-dialog-v2 .ai-crisp-svg{width:100%!important;max-width:100%!important;min-width:0!important}.ai-dialog-v2 .ai-weather-head{min-width:0;flex-wrap:wrap}.ai-dialog-v2 .ai-weather-head>div:first-child{min-width:0}.ai-dialog-v2 .ai-weather-day,.ai-dialog-v2 .ai-weather-hour{flex:0 0 66px}.ai-dialog-v2 .ai-weather-source{max-width:100%;white-space:normal;overflow-wrap:anywhere}}
           @media(max-width:620px){
             .dem-v073{padding:4px;gap:8px}.panel,.schedule-shell,.table-wrap{border-radius:7px}.panel-title{padding:10px 12px;font-size:18px}
             .status-grid,.sales-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px!important;padding:7px!important}.status-panel .stat,.sales-summary .stat{min-height:52px;padding:7px 8px;gap:7px}.status-panel .status-mode{grid-column:1/-1}.stat-icon{width:29px;height:29px}.stat-icon svg{width:17px;height:17px}.status-panel .stat span,.sales-summary .stat span{font-size:10px}.status-panel .stat strong,.sales-summary .stat strong{font-size:13px;line-height:1.25;white-space:normal;overflow-wrap:anywhere}
             .info-grid{gap:8px}.info-grid>.panel{min-height:0;height:auto}.price-summary{grid-template-columns:1fr}.price-scroll{height:230px}.price-table th,.price-table td{padding:4px 7px;font-size:11px}
              .solcast-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.solcast-days{display:flex;max-width:100%;gap:6px;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x proximity;padding-bottom:5px}.solcast-day{min-width:132px;scroll-snap-align:start}.solcast-chart{height:162px;padding-left:5px;padding-right:5px}.solcast-bars{height:138px;min-width:0;width:100%;max-width:100%;grid-template-columns:repeat(24,minmax(0,1fr))}.solcast-performance{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:7px}
             .schedule-shell{padding:7px}.schedule-head{gap:8px}.schedule-title h2{font-size:19px}.schedule-title p{font-size:11px;line-height:1.35}.schedule-tools{display:grid;grid-template-columns:1fr 1fr;gap:6px}.tool-btn{min-height:36px;padding:0 8px;justify-content:center;font-size:12px}.gear-btn{width:100%;min-height:36px}.mode-legend{display:flex;gap:10px;overflow-x:auto;padding:3px 1px 7px;scroll-snap-type:x proximity}.mode-tile{min-width:150px;scroll-snap-align:start}.mode-icon{width:30px;height:30px}.mode-tile strong{font-size:12px}.mode-tile span{font-size:10px}.schedule-table{min-width:880px}.schedule-table th,.schedule-table td{padding:2px 3px}.schedule-table td{font-size:10px}.schedule-foot{padding:7px;align-items:flex-start;flex-direction:column}.foot-actions{width:100%;display:grid;grid-template-columns:1fr 1fr}.foot-actions button{justify-content:center;padding:0 7px;font-size:11px}
             .sales-summary{padding:8px}.sales-chart{min-height:150px}.sales-tables{gap:8px}.sales-table-card h3{font-size:14px;padding:9px}.sales-table-card th,.sales-table-card td{font-size:11px;padding:6px 8px}
              .overlay{padding:0;align-items:stretch}.dialog,.ai-dialog,.settings-dialog{width:100%!important;height:100dvh!important;max-height:100dvh!important;border-radius:0}.dialog-head{padding-top:max(14px,env(safe-area-inset-top))}.dialog-actions{padding-bottom:max(12px,env(safe-area-inset-bottom))}.apply-row{grid-template-columns:24px 1fr}.apply-row .field,.apply-row select{grid-column:2}.ai-grid{grid-template-columns:1fr}.ai-proposal-scroll,.ai-history-scroll{max-height:none}.history-toolbar{grid-template-columns:1fr 1fr}.history-toolbar button{width:100%}.analysis-detail-grid,.analysis-price-groups{grid-template-columns:1fr}.settings-content{padding:9px}.diagnostic-summary{grid-template-columns:1fr}.diagnostic-actions{display:grid}.diagnostic-actions button{width:100%}.ai-main{padding:10px}.ai-price-columns{grid-template-columns:1fr}.ai-kpis,.ai-day-plan>.ai-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.ai-proposal-toolbar{align-items:stretch;flex-direction:column}.ai-day-tabs,.ai-view-tools{display:grid;grid-template-columns:1fr 1fr}.ai-decision-grid{grid-template-columns:1fr}.ai-chart-card{padding:9px}.ai-chart-card svg{min-width:620px}.ai-chart-card{overflow-x:auto}.ai-crisp-chart svg{min-width:0!important}.ai-crisp-chart{overflow:visible}.ai-dialog-v2 .ai-main{padding:10px}.ai-dialog-v2 .ai-overview-grid,.ai-dialog-v2 .ai-price-columns,.ai-dialog-v2 .ai-decision-grid,.ai-dialog-v2 .ai-support-grid,.ai-dialog-v2 .ai-quality-full{grid-template-columns:minmax(0,1fr)}.ai-dialog-v2 .ai-proposal-explainer{grid-template-columns:minmax(0,1fr)}.ai-dialog-v2 .ai-proposal-explainer strong{grid-row:auto}.ai-dialog-v2 .ai-proposal-toolbar{width:100%;max-width:100%;min-width:0}.ai-dialog-v2 .ai-day-tabs,.ai-dialog-v2 .ai-view-tools{width:100%;max-width:100%;min-width:0}.ai-dialog-v2 .ai-day-tabs button,.ai-dialog-v2 .ai-view-tools button{min-width:0;white-space:normal;overflow-wrap:anywhere}.ai-dialog-v2 .ai-chart-card{max-width:100%}.ai-dialog-v2 .ai-crisp-chart{overflow:hidden}.ai-dialog-v2 .ai-crisp-layout{grid-template-columns:30px minmax(0,1fr) 26px}.ai-dialog-v2 .ai-crisp-status{grid-template-columns:58px minmax(0,1fr)}.ai-dialog-v2 .ai-weather-head{display:grid;grid-template-columns:minmax(0,1fr);gap:8px}.ai-dialog-v2 .ai-weather-temperature{text-align:left}.ai-dialog-v2 .ai-weather-facts{grid-template-columns:repeat(2,minmax(0,1fr))}.ai-dialog-v2 .ai-quality-card li{min-width:0;flex-wrap:wrap}.ai-dialog-v2 .ai-quality-card li span,.ai-dialog-v2 .ai-quality-card li strong{min-width:0;overflow-wrap:anywhere}.ai-dialog-v2 .ai-quality-card li strong{text-align:left}
           }
           @media(max-width:620px){.ai-settings-tabs{overflow-x:auto;flex-wrap:nowrap}.ai-settings-tabs button{flex:0 0 auto}.ai-settings-pane .settings-row{grid-template-columns:minmax(0,1fr);gap:7px}.ai-settings-pane .settings-row select,.ai-settings-pane .settings-row .compact-field{max-width:100%;width:100%;justify-self:stretch}.ai-settings-pane .settings-row>input[type=checkbox]{justify-self:start}.ai-weekdays{grid-template-columns:repeat(4,minmax(0,1fr))}.ai-day-presets{justify-content:flex-start}.ai-profile-summary,.ai-hour-detail-grid{grid-template-columns:minmax(0,1fr)}.ai-profile-impact li,.ai-status-list li{min-width:0;flex-wrap:wrap}.ai-profile-impact strong,.ai-status-list strong{text-align:left;min-width:0}.ai-hour-detail{padding:9px}}
           .ai-plan-execution{display:grid;gap:12px;min-width:0}.ai-execution-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.ai-execution-toolbar .ai-day-tabs{display:flex;flex-wrap:wrap;gap:6px}.ai-execution-toolbar .ai-day-tabs button{border-radius:8px;min-height:38px;padding:0 18px;font-weight:700}.ai-execution-date{display:flex;align-items:center;gap:7px}.ai-execution-date input,.ai-execution-date button{min-height:36px;box-sizing:border-box;border:1px solid var(--line2);border-radius:6px;background:#102d42;color:#e7f5fb;padding:0 10px}.ai-execution-date button{cursor:pointer;background:#1b638f}.ai-execution-info{border:1px solid rgba(100,145,170,.35);border-radius:7px;background:rgba(3,20,32,.55);color:#b7cdd9}.ai-execution-info summary{cursor:pointer;padding:7px 11px;font-size:12px;list-style:none;display:flex;align-items:center;gap:6px}.ai-execution-info summary::-webkit-details-marker{display:none}.ai-execution-info p{margin:0;padding:9px 12px;border-top:1px solid rgba(100,145,170,.25);font-size:11px;line-height:1.5;color:#c9dce5}.ai-execution-error{border-left:3px solid #ff6577;background:rgba(255,101,119,.08);padding:12px;color:#ffb1ba}.ai-execution-kpis{display:flex;flex-wrap:wrap;gap:12px}.ai-exec-kpi{flex:1;min-width:150px;display:flex;align-items:center;gap:11px;padding:10px 14px;border:1px solid rgba(103,158,184,.28);border-radius:8px;background:linear-gradient(180deg,rgba(14,38,54,.72),rgba(7,25,38,.75))}.ai-exec-kpi-icon{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;background:rgba(103,158,184,.12)}.ai-exec-kpi-body{flex:1;display:flex;flex-direction:column;min-width:0}.ai-exec-kpi-title{font-size:11px;color:#91adbc}.ai-exec-kpi-row{display:flex;gap:14px;font-size:12px;margin-top:2px}.ai-exec-kpi-pair{display:flex;flex-direction:column;min-width:0}.ai-exec-kpi-pair small{font-size:9px;color:#64748b}.ai-exec-kpi-pair b{font-size:14px;white-space:nowrap}.ai-exec-kpi-plan{color:#e6f5fa}.ai-exec-kpi-wykonanie{color:#7ee22d}.ai-exec-kpi-pv .ai-exec-kpi-icon{color:#7ee22d;background:rgba(126,226,45,.14)}.ai-exec-kpi-pv b{color:#7ee22d}.ai-exec-kpi-dom .ai-exec-kpi-icon{color:#ff9f43;background:rgba(255,159,67,.14)}.ai-exec-kpi-dom b{color:#ff9f43}.ai-exec-kpi-exp .ai-exec-kpi-icon{color:#2ee6c8;background:rgba(46,230,200,.13)}.ai-exec-kpi-exp b{color:#2ee6c8}.ai-exec-kpi-imp .ai-exec-kpi-icon{color:#ff7a85;background:rgba(255,122,133,.13)}.ai-exec-kpi-imp b{color:#ff7a85}.ai-exec-kpi-wynik .ai-exec-kpi-icon{color:#ffd200;background:rgba(255,210,0,.14);font-size:13px;font-weight:800}.ai-exec-kpi-wynik b{color:#ffd200}.ai-exec-kpi-unit{font-size:10px;color:#91adbc;margin-left:2px}.ai-execution-chart{overflow:visible;position:relative}.ai-execution-chart .ai-chart-scroll svg{width:100%;height:auto;display:block;max-height:none;stroke:none}.ai-exec-grid{stroke:rgba(136,184,205,.10);stroke-width:1}.ai-exec-grid-v{stroke:rgba(136,184,205,.12);stroke-width:1;stroke-dasharray:3 4}.ai-exec-baseline{stroke:#9fc0d2;stroke-width:1.5}.ai-execution-chart .ai-now-line{stroke:#ffd200;stroke-width:2;stroke-dasharray:6 5}.ai-execution-chart .ai-now-label{fill:#ffd200;font-weight:800}.ai-chart-tooltip strong span.proposed{color:#70c8ff}.ai-chart-tooltip strong span.approved{color:#ffe071}.ai-chart-tooltip strong span.deployed{color:#c9ee72}.ai-chart-tooltip strong span.done{color:#78ed7d}.ai-chart-tooltip strong span.blocked,.ai-chart-tooltip strong span.cancelled{color:#ff94a2}.ai-chart-tooltip strong span.partial{color:#ffd38a}.ai-chart-tooltip strong span.skipped,.ai-chart-tooltip strong span.missing{color:#a8bdc7}.ai-chart-tooltip .ai-exec-tip-sep{display:block;height:1px;background:rgba(103,158,184,.28);margin:7px 0}.ai-execution-legend,.ai-execution-status-legend{display:flex;justify-content:center;flex-wrap:wrap;gap:7px 13px;color:#a9c2ce;font-size:10px}.ai-execution-legend span{display:inline-flex;align-items:center;gap:5px}.ai-execution-legend i{display:inline-block;width:12px;height:7px;border-radius:2px}.ai-execution-legend .pv-plan i{background:#7cb342}.ai-execution-legend .pv-wykonanie i{background:#00e676}.ai-execution-legend .load-plan i{background:#ff9f43}.ai-execution-legend .load-wykonanie i{background:#42a5f5}.ai-execution-legend .soc-plan i{height:3px;background:#ffd200}.ai-execution-legend .soc-wykonanie i{height:3px;background:#f4f7f9}.ai-exec-pv-plan,.ai-exec-load-plan,.ai-exec-export-plan,.ai-exec-import-plan{opacity:.75}.ai-exec-pv-plan{fill:url(#aiExecGradPvPlan)}.ai-exec-pv-wykonanie{fill:url(#aiExecGradPvWyk)}.ai-exec-load-plan{fill:url(#aiExecGradLoadPlan)}.ai-exec-load-wykonanie{fill:url(#aiExecGradLoadWyk)}.ai-exec-export-plan{fill:url(#aiExecGradExportPlan)}.ai-exec-export-wykonanie{fill:url(#aiExecGradExportWyk)}.ai-exec-import-plan{fill:url(#aiExecGradImportPlan)}.ai-exec-import-wykonanie{fill:url(#aiExecGradImportWyk)}.ai-exec-soc-plan{fill:none;stroke:#ffd200;stroke-width:2.8}.ai-exec-soc-wykonanie{fill:none;stroke:#f4f7f9;stroke-width:2;stroke-dasharray:5 4}.ai-exec-status{fill:#435967}.ai-exec-status.proposed{fill:#42a5f5}.ai-exec-status.approved{fill:#ffd200}.ai-exec-status.deployed{fill:#8aaa2d}.ai-exec-status.done{fill:#69d438}.ai-exec-status.partial{fill:#d4932c}.ai-exec-status.blocked,.ai-exec-status.cancelled{fill:#ff5252}.ai-execution-status-legend span,.ai-exec-badge{border-radius:999px;padding:3px 8px;font-weight:800;font-size:10px;white-space:nowrap}.ai-execution-status-legend .proposed,.ai-exec-badge.proposed{color:#70c8ff;background:rgba(56,135,185,.2)}.ai-execution-status-legend .approved,.ai-exec-badge.approved{color:#ffe071;background:rgba(157,124,40,.2)}.ai-execution-status-legend .deployed,.ai-exec-badge.deployed{color:#c9ee72;background:rgba(138,170,45,.2)}.ai-execution-status-legend .done,.ai-exec-badge.done{color:#78ed7d;background:rgba(66,189,71,.2)}.ai-execution-status-legend .blocked,.ai-exec-badge.blocked,.ai-exec-badge.cancelled{color:#ff94a2;background:rgba(195,68,85,.2)}.ai-exec-badge.partial{color:#ffd38a;background:rgba(212,147,44,.2)}.ai-exec-badge.skipped,.ai-exec-badge.missing{color:#a8bdc7;background:rgba(91,120,134,.18)}.ai-empty-state{display:grid;place-items:center;gap:8px;padding:34px 18px;text-align:center;color:#a9c2ce;border:1px dashed rgba(103,158,184,.35);border-radius:9px;background:rgba(3,16,25,.42)}.ai-empty-state strong{color:#d8ebf4;font-size:14px}.ai-empty-state span{display:block}.ai-empty-icon{font-size:32px;line-height:1}.ai-empty-error{border-color:rgba(255,95,112,.45);background:rgba(120,24,39,.22)}.ai-execution-table{min-width:1240px;border-collapse:separate;border-spacing:0;font-size:11px}.ai-execution-table thead{position:sticky;top:0;z-index:3}.ai-execution-table tfoot{position:sticky;bottom:0;z-index:2}.ai-execution-table th,.ai-execution-table td{padding:5px 6px;border-bottom:1px solid rgba(103,158,184,.15);text-align:center;white-space:nowrap}.ai-execution-table th{background:rgba(8,28,42,.92);color:#c6e0ec;font-weight:800}.ai-execution-table tbody tr:hover{background:rgba(21,155,255,.08)}.ai-exec-odd{background:rgba(255,255,255,.025)}.ai-exec-head-main th{border-bottom:0;padding:8px 6px}.ai-exec-head-sub th{padding:4px 6px;font-size:10px;color:#9ab7c6;border-top:0}th.ai-exec-group-pv{border-top:2px solid rgba(124,195,66,.5)}th.ai-exec-group-dom{border-top:2px solid rgba(255,159,67,.5)}th.ai-exec-group-imp{border-top:2px solid rgba(255,82,82,.5)}th.ai-exec-group-exp{border-top:2px solid rgba(0,229,255,.5)}.ai-exec-col-hour{position:sticky;left:0;z-index:4;background:rgba(8,28,42,.97);width:72px;box-sizing:border-box;box-shadow:1px 0 0 rgba(103,158,184,.15)}.ai-exec-col-status{position:sticky;left:72px;z-index:4;background:rgba(8,28,42,.97);width:94px;box-sizing:border-box;box-shadow:1px 0 0 rgba(103,158,184,.15)}.ai-exec-col-action{position:sticky;left:166px;z-index:4;background:rgba(8,28,42,.97);width:122px;box-sizing:border-box;text-align:left;box-shadow:1px 0 0 rgba(103,158,184,.15)}.ai-exec-col-power{position:sticky;left:288px;z-index:4;background:rgba(8,28,42,.97);width:82px;box-sizing:border-box;box-shadow:1px 0 0 rgba(103,158,184,.15)}.ai-exec-col-error{min-width:72px}.ai-exec-summary td{background:rgba(8,28,42,.96);font-weight:800;color:#7ee22d;border-top:2px solid rgba(126,226,45,.35)}.ai-exec-summary strong{color:#7ee22d}.ai-exec-action{display:block;color:#e6f5fa}.ai-exec-source{display:block;font-size:9px;color:#7a9aad;margin-top:1px}.ai-exec-unit{font-size:9px;color:#7a9aad}.ai-exec-price-sell{color:#ff7a85}.ai-exec-price-buy{color:#bd6dff}.ai-exec-price-sep,.ai-exec-error-sep{color:#5e7d8c;margin:0 3px}.ai-exec-wykonanie{color:#c9dce5}.ai-exec-wykonanie-match{color:#a8f0c6}.ai-exec-wykonanie-off{color:#ffd38a}.ai-exec-wykonanie-diverge{color:#ff94a2}.ai-execution-table-wrap{max-height:430px;overflow:auto!important;border:1px solid rgba(103,158,184,.28);border-radius:8px;background:rgba(3,14,23,.42)}
            @media(max-width:620px){.ai-execution-toolbar,.ai-execution-date{width:100%}.ai-execution-date{display:grid;grid-template-columns:minmax(0,1fr) auto}.ai-exec-kpi{min-width:calc(50% - 4px)}.ai-execution-chart{padding:8px}.ai-execution-toolbar .ai-day-tabs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}}
@media(max-width:620px){.ai-execution-toolbar,.ai-execution-date{width:100%}.ai-execution-date{display:grid;grid-template-columns:minmax(0,1fr) auto}.ai-exec-kpi{min-width:calc(50% - 4px)}.ai-execution-chart{padding:8px}.ai-execution-toolbar .ai-day-tabs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}}
           .ai-explanation-view{display:grid;gap:12px}.ai-explanation-view>h2{margin:0}.ai-explanation-profile details,.ai-shadow,.ai-help{margin-top:10px}.ai-explanation-profile summary,.ai-shadow summary,.ai-help summary{cursor:pointer;color:#dff3fc;font-weight:800}.ai-decision-summary{line-height:1.55}.ai-explanation-balance{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:10px 0}.ai-explanation-balance>div{border:1px solid rgba(103,158,184,.2);border-radius:6px;padding:9px;background:rgba(3,16,25,.45)}.ai-explanation-balance span{display:block;color:#93adbc;font-size:10px}.ai-explanation-balance strong{display:block;margin-top:4px}.ai-explanation-list{display:grid;gap:7px;padding-left:18px}.ai-explanation-list li{padding:6px 0;border-top:1px solid rgba(103,158,184,.15)}.ai-explanation-list strong{display:block;color:#7ee22d}.ai-explanation-list span{display:block;margin-top:3px;color:#b9d0dc;line-height:1.4}.ai-help dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:7px 12px}.ai-help dt{color:#7ee22d;font-weight:800}.ai-help dd{margin:0;color:#b9d0dc}@media(max-width:620px){.ai-explanation-balance{grid-template-columns:minmax(0,1fr)}.ai-help dl{grid-template-columns:minmax(0,1fr)}}
           </style>
            <div class="dem-v073" style="${demStyle}">
            ${statusSection}
            ${infoGridSection}
            ${scheduleSection}
            ${salesSection}
          </div>
          <div class="dialog-host">${this.renderDialog(slots, touStarts)}</div>
      </ha-card>`;

    this._lastSlots = slots;
    this._lastTouStarts = touStarts;
    this._scheduleEntityIds = this.scheduleEntityIds(slots);
    this._lastScheduleSignature = this.scheduleStateSignature();

    this.bindControlsV073(slots);
    this._isRendered = true;
    this.scaleFlowPanel();
    this.syncBulkPanelValues(slots);
    this.restoreScrollPositions();
  }

  bindControlsV073(slots) {
    this.bindDashboardControls(slots);
    this.bindDialogControls(slots);
  }

  bindDashboardControls(slots) {
    const root = this.querySelector(".dem-v073") || this;
    root.querySelectorAll("[data-control-toggle]").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        this.toggleControl();
      });
    });
    root.querySelectorAll("[data-toggle]").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        this.toggle(el.dataset.toggle);
      });
    });
    root.querySelectorAll("[data-number]").forEach((el) => {
      el.onchange = () => this.setNumber(el.dataset.number, el.value);
      el.onkeydown = (event) => {
        if (event.key === "Enter") {
          this.setNumber(el.dataset.number, el.value);
          el.blur();
        }
      };
    });
    root.querySelectorAll("[data-select]").forEach((el) => {
      el.value = this.state(el.dataset.select);
      // Ładowanie jest wyborem trybu pracy. Zgoda na Grid pozostaje osobna
      // explicit consent and must never be inferred from this selection.
      el.onchange = () => this.setSelect(el.dataset.select, el.value);
    });
    root.querySelectorAll("[data-time]").forEach((el) => {
      el.onchange = () => this.setTime(el.dataset.time, el.value);
    });
    root.querySelectorAll("[data-slot-check]").forEach((el) => {
      el.addEventListener("click", (event) => event.stopPropagation());
      el.addEventListener("change", () => {
        if (!this._selectionMode) this._selectedSlots.clear();
        if (el.checked) this._selectedSlots.add(el.dataset.slotCheck);
        else this._selectedSlots.delete(el.dataset.slotCheck);
        this._selectionMode = true;
        this.resetBulkEditState();
        this.render();
      });
    });
    root.querySelectorAll("[data-slot-row]").forEach((el) => el.addEventListener("click", (event) => {
      if (event.target.closest("button,input,select,label")) return;
      const key = el.dataset.slotRow;
      if (this._selectionMode) {
        if (this._selectedSlots.has(key)) this._selectedSlots.delete(key);
        else this._selectedSlots.add(key);
        this.resetBulkEditState();
        this.render();
        return;
      }
      event.preventDefault();
      this.captureScrollPositions();
      const label = slots.find(([slotKey]) => slotKey === key)?.[1] || "";
      this.openScheduleSlotEditor(key, label, "sell");
      this.render();
    }));
    root.querySelectorAll("[data-open-slot]").forEach((el) => el.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      this.captureScrollPositions();
      const [type, key] = el.dataset.openSlot.split(":");
      const label = slots.find(([slotKey]) => slotKey === key)?.[1] || "";
      this.openScheduleSlotEditor(key, label, type);
      this.render();
    }));
    root.querySelectorAll("[data-open-tou]").forEach((el) => el.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      this.captureScrollPositions();
      this.openTouEditor(Number(el.dataset.openTou));
      this.render();
    }));
    root.querySelectorAll("[data-save-tou]").forEach((el) => el.addEventListener("click", () => {
      this.savePhysicalTouSlot(Number(el.dataset.saveTou));
    }));
    root.querySelectorAll("[data-open-ai]").forEach((el) => el.addEventListener("click", (event) => {
      event.preventDefault();
      this.captureScrollPositions();
      this.saveAiAnalysis(this.aiSuggestions(slots));
      this._aiView = "proposals";
      this._aiDay = "today";
      this._aiShow24 = false;
      this.initialiseAiSelections(this.aiPlannerData(slots));
      this._dialog = { type: "ai" };
      this.render();
    }));
    root.querySelectorAll("[data-open-settings]").forEach((el) => el.addEventListener("click", (event) => {
      event.preventDefault();
      this.captureScrollPositions();
      const tab = el.dataset.openSettings;
      this._settingsTab = tab && tab !== "1" ? tab : "defaults";
      this._dialog = { type: "settings" };
      this.render();
    }));
    root.querySelectorAll("[data-toggle-selection]").forEach((el) => el.addEventListener("click", () => {
      this._selectionMode = !this._selectionMode;
      this._selectedSlots.clear();
      this.resetBulkEditState();
      this.render();
    }));
    root.querySelectorAll("[data-schedule-select-all]").forEach((el) => el.addEventListener("click", () => {
      slots.forEach(([key]) => this._selectedSlots.add(key));
      this._selectionMode = true;
      this.resetBulkEditState();
      this.render();
    }));
    root.querySelectorAll("[data-schedule-clear]").forEach((el) => el.addEventListener("click", () => {
      this._selectedSlots.clear();
      this._dialog = null;
      this.resetBulkEditState();
      this.render();
    }));
    root.querySelectorAll("[data-open-multi]").forEach((el) => el.addEventListener("click", () => {
      if (!this.selectedSlotList(slots).length) return;
      this._selectionMode = true;
      this.render();
    }));
    root.querySelectorAll("[data-apply-field],[data-raw^='multi-']").forEach((el) => {
      const saveBulkDraft = () => this.collectBulkEditState();
      el.addEventListener("change", saveBulkDraft);
      if (el.tagName !== "SELECT" && el.type !== "checkbox") el.addEventListener("input", saveBulkDraft);
    });
    root.querySelectorAll("[data-apply-multi]").forEach((el) => el.addEventListener("click", () => this.applyMultiEdit(slots)));
  }

  bindDialogControls(slots) {
    const root = this.querySelector(".dialog-host") || this;
    root.querySelectorAll("[data-close-dialog]").forEach((el) => {
      el.addEventListener("click", (event) => {
        if (el.classList.contains("overlay") && event.target !== el) return;
        event.preventDefault();
        event.stopPropagation();
        this.closeDialog();
      });
    });
    root.querySelectorAll("[data-toggle]").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        this.toggle(el.dataset.toggle);
      });
    });
    root.querySelectorAll("[data-number]").forEach((el) => {
      el.onchange = () => this.setNumber(el.dataset.number, el.value);
      el.onkeydown = (event) => {
        if (event.key === "Enter") {
          this.setNumber(el.dataset.number, el.value);
          el.blur();
        }
      };
    });
    root.querySelectorAll("[data-select]").forEach((el) => {
      el.value = this.state(el.dataset.select);
      // Ładowanie jest wyborem trybu pracy. Zgoda na Grid pozostaje osobna
      // explicit consent and must never be inferred from this selection.
      el.onchange = () => this.setSelect(el.dataset.select, el.value);
    });
    root.querySelectorAll("[data-time]").forEach((el) => {
      el.onchange = () => this.setTime(el.dataset.time, el.value);
    });
    root.querySelectorAll("[data-slot-draft-field]").forEach((el) => {
      const update = () => {
        this.updateSlotDraftField(el.dataset.slotDraftField, el.value);
        if (el.dataset.slotDraftField === "mode") this.renderDialogOnly();
      };
      el.addEventListener("change", update);
      if (el.tagName !== "SELECT") el.addEventListener("input", update);
    });
    root.querySelectorAll("[data-save-slot-edit]").forEach((el) => el.addEventListener("click", () => this.saveScheduleSlotDraft()));
    root.querySelectorAll("[data-cancel-slot-edit]").forEach((el) => el.addEventListener("click", () => this.cancelScheduleSlotEdit()));
    root.querySelectorAll("[data-discard-slot-edit]").forEach((el) => el.addEventListener("click", () => this.discardScheduleSlotChanges()));
    root.querySelectorAll("[data-return-slot-edit]").forEach((el) => el.addEventListener("click", () => this.returnToScheduleSlotEditing()));
    root.querySelectorAll("[data-draft-normal-profile]").forEach((el) => el.addEventListener("click", () => {
      this.applyProfileToSlotDraft("Normalna Praca", true);
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-draft-charge-profile]").forEach((el) => el.addEventListener("click", () => {
      this.applyProfileToSlotDraft("Ładowanie", true);
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-tou-field]").forEach((el) => {
      const update = () => {
        if (this._dialog?.type === "tou") this.collectTouEditorDraft(Number(this._dialog.idx));
      };
      el.addEventListener("change", update);
      if (el.tagName !== "SELECT") el.addEventListener("input", update);
    });
    root.querySelectorAll("[data-save-tou]").forEach((el) => el.addEventListener("click", () => {
      this.savePhysicalTouSlot(Number(el.dataset.saveTou));
    }));
    root.querySelectorAll("[data-settings-tab]").forEach((el) => el.addEventListener("click", () => {
      this._settingsTab = el.dataset.settingsTab;
      this._tariffDraft = null;
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-settings-section]").forEach((el) => el.addEventListener("click", () => {
      this.collectAiProfiles();
      this._aiSettingsSection = el.dataset.aiSettingsSection;
      this._aiProfileStatus = "";
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-profile][data-ai-profile-field]").forEach((el) => {
      const update = () => this.collectAiProfiles();
      el.addEventListener("change", update);
      if (el.tagName !== "SELECT" && el.type !== "checkbox") el.addEventListener("input", update);
    });
    root.querySelectorAll("[data-ai-profile-day]").forEach((el) => el.addEventListener("change", () => this.collectAiProfiles()));
    root.querySelectorAll("[data-ai-profile-days]").forEach((el) => el.addEventListener("click", () => {
      const selected = new Set(String(el.dataset.days || "").split(",").filter(Boolean));
      this.querySelectorAll(`[data-ai-profile-day="${el.dataset.aiProfileDays}"]`).forEach((box) => {
        box.checked = !selected.size || selected.has(box.value);
      });
      const draft = this.collectAiProfiles();
      draft.profiles[el.dataset.aiProfileDays].active_days = selected.size ? [...selected] : [];
    }));
    root.querySelectorAll("[data-save-ai-profiles]").forEach((el) => el.addEventListener("click", () => this.saveAiProfiles()));
    root.querySelectorAll("[data-ai-api-field]").forEach((el) => {
      const update = () => {
        this.collectAiApiDraft();
        if (el.dataset.aiApiField === "provider") this.renderDialogOnly();
      };
      el.addEventListener("change", update);
      if (el.tagName !== "SELECT" && el.type !== "checkbox" && el.dataset.aiApiField !== "api_key") {
        el.addEventListener("input", update);
      }
    });
    root.querySelectorAll("[data-save-ai-api]").forEach((el) => el.addEventListener("click", () => this.saveAiApiSettings()));
    root.querySelectorAll("[data-test-ai-api]").forEach((el) => el.addEventListener("click", () => this.runAiApiService("test_ai_api")));
    root.querySelectorAll("[data-analyze-ai-api]").forEach((el) => el.addEventListener("click", () => this.runAiApiService("analyze_ai_api")));
    root.querySelectorAll("[data-tariff-field='osd_provider'],[data-tariff-field='tariff_plan'],[data-tariff-field='buy_seller_id'],[data-tariff-field='buy_seller_tariff_id']").forEach((el) => el.addEventListener("change", () => {
      const draft = this.collectTariffDraft();
      if (el.dataset.tariffField === "osd_provider") {
        const provider = this.tariffData().providers?.find((item) => item.id === draft.osd_provider);
        if (provider?.tariffs?.length) draft.tariff_plan = provider.tariffs[0].id;
      }
      if (["osd_provider", "tariff_plan", "buy_seller_id"].includes(el.dataset.tariffField)) {
        draft.buy_seller_tariff_id = "";
      }
      this._tariffDraft = draft;
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-save-tariff]").forEach((el) => el.addEventListener("click", () => this.saveTariffSettings()));
    root.querySelectorAll("[data-refresh-tariff]").forEach((el) => el.addEventListener("click", async () => {
      el.disabled = true;
      try {
        await this.callService("deye_energy_manager", "refresh_tariff_catalog", {});
        this._tariffSaveStatus = "Sprawdzono katalog. Aktywna pozostaje najnowsza poprawna wersja.";
      } catch (error) {
        this._tariffSaveStatus = `Nie udało się sprawdzić katalogu: ${error?.message || error}`;
      }
      this.render();
    }));
    root.querySelectorAll("[data-apply-multi]").forEach((el) => el.addEventListener("click", () => this.applyMultiEdit(slots)));
    root.querySelectorAll("[data-action='apply-defaults']").forEach((el) => el.addEventListener("click", () => this.restoreDefaults()));
    root.querySelectorAll("[data-save-charge-profile]").forEach((el) => el.addEventListener("click", () => this.saveChargeProfile()));
    root.querySelectorAll("[data-save-normal-profile]").forEach((el) => el.addEventListener("click", () => this.saveNormalProfile()));
    root.querySelectorAll("[data-reload-normal-profile]").forEach((el) => el.addEventListener("click", () => {
      this.reloadNormalProfileSlot(el.dataset.reloadNormalProfile);
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-reload-charge-profile]").forEach((el) => el.addEventListener("click", () => {
      this.reloadChargeProfileSlot(el.dataset.reloadChargeProfile);
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-save-default-settings]").forEach((el) => el.addEventListener("click", () => this.saveDefaultSettings()));
    root.querySelectorAll("[data-charge-profile-number]").forEach((el) => {
      const saveDraft = () => { this._chargeProfileDraft[el.dataset.chargeProfileNumber] = el.value; };
      el.addEventListener("input", saveDraft);
      el.addEventListener("change", saveDraft);
    });
    root.querySelectorAll('[data-raw="charge-profile-grid"]').forEach((el) => {
      el.addEventListener("change", () => { this._chargeProfileGridDraft = el.value === "on"; });
    });
    root.querySelectorAll("[data-normal-profile-number]").forEach((el) => {
      const saveDraft = () => { this._normalProfileDraft[el.dataset.normalProfileNumber] = el.value; };
      el.addEventListener("input", saveDraft);
      el.addEventListener("change", saveDraft);
    });
    root.querySelectorAll('[data-raw="normal-profile-mode"]').forEach((el) => {
      el.addEventListener("change", () => { this._normalProfileDraft.physical_work_mode = el.value; });
    });
    root.querySelectorAll('[data-raw="default-work-mode"]').forEach((el) => {
      el.addEventListener("change", () => { this._defaultSettingsDraft.mode = el.value; });
    });
    root.querySelectorAll('[data-raw="default-physical-work-mode"]').forEach((el) => {
      el.addEventListener("change", () => { this._defaultSettingsDraft.physical_work_mode = el.value; });
    });
    root.querySelectorAll("[data-default-profile-number]").forEach((el) => {
      const saveDraft = () => { this._defaultSettingsDraft[el.dataset.defaultProfileNumber] = el.value; };
      el.addEventListener("input", saveDraft);
      el.addEventListener("change", saveDraft);
    });
    root.querySelectorAll("[data-action='select-all']").forEach((el) => el.addEventListener("click", () => {
      slots.forEach(([key]) => this._selectedSlots.add(key));
      this._selectionMode = true;
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-action='clear-selected']").forEach((el) => el.addEventListener("click", () => {
      this._selectedSlots.clear();
      this.renderDialogOnly();
    }));
    const saveAiValue = (el) => {
      const settings = this.aiSettings();
      const key = el.dataset.aiSetting;
      if (el.type === "checkbox") {
        settings[key] = el.checked;
      } else if (el.tagName === "SELECT") {
        settings[key] = el.value;
      } else {
        const parsed = this.asNumber(el.value);
        settings[key] = parsed === null ? el.value : parsed;
      }
      this.saveAiSettings(settings);
    };
    root.querySelectorAll("[data-ai-setting]").forEach((el) => {
      el.addEventListener("change", () => saveAiValue(el));
      if (el.tagName !== "SELECT" && el.type !== "checkbox") {
        el.addEventListener("input", () => saveAiValue(el));
      }
    });
    root.querySelectorAll("[data-clear-ai-history]").forEach((el) => el.addEventListener("click", () => {
      this.clearAiHistory();
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-history-filter]").forEach((el) => el.addEventListener("change", () => {
      this._historyFilters = { ...(this._historyFilters || {}), [el.dataset.historyFilter]: el.value };
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-export-history]").forEach((el) => el.addEventListener("click", () => this.exportHistory(el.dataset.exportHistory)));
    root.querySelectorAll("[data-export-monthly]").forEach((el) => el.addEventListener("click", () => this.exportMonthlyReport()));
    root.querySelectorAll("[data-rate-history]").forEach((el) => el.addEventListener("click", () => {
      const timestamp = Number(el.dataset.rateHistory);
      const rating = Number(el.dataset.rating);
      this.callService("deye_energy_manager", "rate_ai_analysis", { timestamp, rating });
      const item = this.aiHistory().find((entry) => Number(entry.timestamp) === timestamp);
      if (item) item.rating = rating;
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-clear-all-history]").forEach((el) => el.addEventListener("click", () => {
      if (!window.confirm("Usunąć historię sugestii, dane uczenia i porównania Solcast? Tej operacji nie można cofnąć.")) return;
      this._aiHistoryCache = [];
      this.callService("deye_energy_manager", "clear_history", {});
      try { localStorage.removeItem("deye_energy_manager_ai_history_v073"); } catch (_err) { /* ignored */ }
      this.render();
    }));
    root.querySelectorAll("[data-resume-manager]").forEach((el) => el.addEventListener("click", () => {
      if (window.confirm("W\u0142\u0105czy\u0107 Manager i harmonogram? Nie w\u0142\u0105czy to harmonogramu \u0142adowania z sieci.")) this.resumeManager();
    }));
    root.querySelectorAll("[data-system-defaults]").forEach((el) => el.addEventListener("click", () => {
      if (window.confirm("Zatrzymać managera i zastosować ustawienia domyślne?")) this.restoreDefaults();
    }));
    root.querySelectorAll("[data-refresh-entities]").forEach((el) => el.addEventListener("click", () => this.refreshConfiguredEntities()));
    root.querySelectorAll("[data-export-config]").forEach((el) => el.addEventListener("click", () => this.exportConfiguration()));
    root.querySelectorAll("[data-create-backup]").forEach((el) => el.addEventListener("click", () => {
      try { this.createConfigurationBackup(); } catch (error) { window.alert(`Nie udało się utworzyć kopii: ${error.message}`); }
    }));
    root.querySelectorAll("[data-restore-backup]").forEach((el) => el.addEventListener("click", async () => {
      if (!window.confirm("Przywrócić ostatnią lokalną kopię zapasową? Bieżące ustawienia zostaną zastąpione.")) return;
      try { await this.restoreConfigurationBackup(); window.alert("Kopia zapasowa została przywrócona."); } catch (error) { window.alert(error.message); }
    }));
    root.querySelectorAll("[data-restore-defaults]").forEach((el) => el.addEventListener("click", () => {
      if (window.confirm("Przywrócić ustawienia domyślne i zatrzymać harmonogram?")) this.restoreDefaults();
    }));
    root.querySelectorAll("[data-import-config-open]").forEach((el) => el.addEventListener("click", () => root.querySelector("[data-import-config]")?.click()));
    root.querySelectorAll("[data-import-config]").forEach((el) => el.addEventListener("change", async () => {
      const file = el.files?.[0];
      if (!file) return;
      try {
        const snapshot = JSON.parse(await file.text());
        if (!window.confirm(`Zaimportować konfigurację z pliku ${file.name}?`)) return;
        await this.applyConfigurationSnapshot(snapshot);
        window.alert("Konfiguracja została zaimportowana.");
      } catch (error) {
        window.alert(`Błąd importu: ${error.message}`);
      } finally {
        el.value = "";
      }
    }));
    root.querySelectorAll("[data-ai-view]").forEach((el) => el.addEventListener("click", () => {
      this._aiView = el.dataset.aiView;
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-day]").forEach((el) => el.addEventListener("click", () => {
      this._aiDay = el.dataset.aiDay;
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-explanation-day]").forEach((el) => el.addEventListener("click", () => {
      this._aiExplanationDay = el.dataset.aiExplanationDay === "tomorrow" ? "tomorrow" : "today";
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-execution-range]").forEach((el) => el.addEventListener("click", () => {
      this._aiExecutionRange = el.dataset.aiExecutionRange || "today";
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-execution-date]").forEach((el) => el.addEventListener("change", () => {
      this._aiExecutionDate = el.value;
      this._aiExecutionData = null;
      this._aiExecutionError = "";
    }));
    root.querySelectorAll("[data-ai-execution-load]").forEach((el) => el.addEventListener("click", () => {
      const input = root.querySelector("[data-ai-execution-date]");
      this.loadAiExecutionDay(input?.value || this._aiExecutionDate);
    }));
    root.querySelectorAll("[data-ai-weather-mode]").forEach((el) => el.addEventListener("click", () => {
      this._aiWeatherMode = el.dataset.aiWeatherMode === "hourly" ? "hourly" : "daily";
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-chart-series]").forEach((el) => el.addEventListener("click", () => {
      if (!(this._aiChartHiddenSeries instanceof Set)) this._aiChartHiddenSeries = new Set();
      const series = el.dataset.aiChartSeries;
      if (this._aiChartHiddenSeries.has(series)) this._aiChartHiddenSeries.delete(series);
      else this._aiChartHiddenSeries.add(series);
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-chart-point]").forEach((el) => {
      const show = (event, pin = false) => {
        const card = el.closest("[data-ai-chart]");
        if (!card) return;
        const chartId = el.dataset.aiChartPoint;
        const index = el.dataset.aiChartIndex;
        const key = `${chartId}-${index}`;
        if (pin) this._aiChartPinned = this._aiChartPinned === key ? null : key;
        const source = card.querySelector(`[data-ai-tip-source="${key}"]`);
        const tooltip = card.querySelector("[data-ai-chart-tooltip]");
        const svg = card.querySelector("svg");
        const crossX = card.querySelector(".ai-chart-crosshair-x");
        const crossY = card.querySelector(".ai-chart-crosshair-y");
        if (!source || !tooltip || !svg || !crossX || !crossY) return;
        tooltip.innerHTML = source.innerHTML;
        tooltip.classList.add("visible");
        const x = Number(el.getAttribute("x")) + Number(el.getAttribute("width")) / 2;
        const svgRect = svg.getBoundingClientRect();
        const viewBox = svg.viewBox.baseVal;
        const pointerY = event?.clientY ? (event.clientY - svgRect.top) / svgRect.height * viewBox.height : 150;
        crossX.setAttribute("x1", x); crossX.setAttribute("x2", x);
        const hitTop = Number(el.getAttribute("y")) || 48;
        const hitBottom = hitTop + (Number(el.getAttribute("height")) || 338);
        crossY.setAttribute("y1", Math.max(hitTop, Math.min(hitBottom, pointerY))); crossY.setAttribute("y2", Math.max(hitTop, Math.min(hitBottom, pointerY)));
        crossX.classList.add("visible"); crossY.classList.add("visible");
        const cardRect = card.getBoundingClientRect();
        const pointerX = event?.clientX || cardRect.left + cardRect.width / 2;
        const pointerClientY = event?.clientY || cardRect.top + 180;
        const maxLeft = Math.max(8, cardRect.width - 300);
        tooltip.style.left = `${Math.max(8, Math.min(maxLeft, pointerX - cardRect.left + 14))}px`;
        tooltip.style.top = `${Math.max(52, Math.min(cardRect.height - 300, pointerClientY - cardRect.top + 12))}px`;
        this.holdInteraction(1400);
      };
      const hide = () => {
        const key = `${el.dataset.aiChartPoint}-${el.dataset.aiChartIndex}`;
        if (this._aiChartPinned === key) return;
        const card = el.closest("[data-ai-chart]");
        card?.querySelector("[data-ai-chart-tooltip]")?.classList.remove("visible");
        card?.querySelector(".ai-chart-crosshair-x")?.classList.remove("visible");
        card?.querySelector(".ai-chart-crosshair-y")?.classList.remove("visible");
      };
      el.addEventListener("pointerenter", (event) => show(event));
      el.addEventListener("pointermove", (event) => show(event));
      el.addEventListener("pointerleave", hide);
      el.addEventListener("click", (event) => { event.stopPropagation(); show(event, true); });
    });
    root.querySelectorAll("[data-ai-toggle-24]").forEach((el) => el.addEventListener("click", () => {
      this._aiShow24 = !this._aiShow24;
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-plan-row]").forEach((el) => el.addEventListener("change", () => {
      const selected = this.aiSelection();
      if (el.checked) selected.add(el.dataset.aiPlanRow);
      else selected.delete(el.dataset.aiPlanRow);
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-hour-detail]").forEach((el) => el.addEventListener("click", (event) => {
      if (event.target.closest("input,button,a")) return;
      this._aiDetailKey = el.dataset.aiHourDetail;
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-ai-toggle-selection]").forEach((el) => el.addEventListener("click", () => {
      const planner = this.aiPlannerData(slots);
      const proposedKeys = this.aiRowsForDay(planner).filter((row) => this.aiCanSelectProposal(planner, row)).map((row) => this.aiSlotKey(row.hour));
      const selected = this.aiSelection();
      const allSelected = proposedKeys.length && proposedKeys.every((key) => selected.has(key));
      if (allSelected) selected.clear();
      else proposedKeys.forEach((key) => selected.add(key));
      this.renderDialogOnly();
    }));
    root.querySelectorAll("[data-apply-ai-day]").forEach((el) => el.addEventListener("click", () => this.applyAiDayPlan(slots)));
    root.querySelectorAll("[data-cancel-future-plan]").forEach((el) => el.addEventListener("click", async () => {
      if (!window.confirm("Anulować zapisany plan na jutro?")) return;
      await this.callService("deye_energy_manager", "cancel_future_plan", {});
      this.render();
    }));
  }

  renderDialogOnly() {
    if (!this._lastSlots) return;
    const host = this.querySelector(".dialog-host");
    if (!host) return;
    this.captureScrollPositions();
    host.innerHTML = this.renderDialog(this._lastSlots, this._lastTouStarts);
    this.bindDialogControls(this._lastSlots);
    this.restoreScrollPositions();
  }

  render() {
    return this.renderV073();
  }
}

customElements.define("deye-energy-manager-card", DeyeEnergyManagerCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "deye-energy-manager-card", name: "Deye Energy Manager", description: "Deye Energy Manager 0.8.0" });
