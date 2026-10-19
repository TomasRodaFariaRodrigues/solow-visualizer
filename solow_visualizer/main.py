import itertools
import sys
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

import sv_ttk
from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import to_hex
from matplotlib.figure import Figure

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from solow_visualizer import (
    diagram,
    simplesolow,
    solowtech,
    solowtechhcap,
    transition,
)
from solow_visualizer.registry import REGISTRY, ParamSpec, Series, Shock


def _default_instrument(entry):
    """Determines the default instrument for the transition view: s or first parameter"""
    names = [spec.name for spec in entry.params]
    return "s" if "s" in names else (names[0] if names else "")


#####################################################################
### UI-related variables for easy tweaking in case of visual bugs ###
#####################################################################

SIDEBAR_WIDTH = 400  # Sidebar width in pixels
SIDEBAR_PADDING = 8
SIDEBAR_INNER = SIDEBAR_WIDTH - 2 * SIDEBAR_PADDING
SCROLL_MARGIN = 20
PARAM_VALUE_WIDTH = 110  # Spinbox width in pixels
MIN_WRAP = 300
ROW_HEIGHT = 22
SWATCH_SIZE = 12  # Color square size in pixels
SWATCH_COL_WIDTH = 36
SHOWN_COL_WIDTH = 52
SHOWN_COLUMN = "#2"  # Display id of the "shown" column
SELECTED_CONTRAST = 0.28
MUTED_FADE = 0.45
HIDDEN_FADE = 0.55

# Change of setting to create more space in Treeview
SWATCH_STYLE = "Swatch.Treeview"
SWATCH_ITEM_LAYOUT = [
    (
        "Treeitem.padding",
        {
            "sticky": "nswe",
            "children": [
                ("Treeitem.image", {"sticky": ""}),
            ],
        },
    ),
]

# Limit on policy instrument for transition view
AMOUNT_SPEC = ParamSpec("amount", "by", 0.1, 0.0, 10.0, 0.01)


#####################################################################
###               UI structure - Built using Tkinter              ###
#####################################################################


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Solow Model Visualizer")

        self.dpi = round(self.winfo_fpixels("1i"))
        self._scale = self.dpi / 96
        self._font_bases = {}

        width, height = self.px(1400), self.px(800)
        width = min(width, self.winfo_screenwidth() - self.px(80))
        height = min(height, self.winfo_screenheight() - self.px(120))
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)

        self.entries = list(REGISTRY.values())
        self._color_cycles = {e.key: itertools.cycle(rcParams["axes.prop_cycle"].by_key()["color"]) for e in self.entries}
        self.series_by_model = {e.key: [] for e in self.entries}
        self.param_vars = {}
        self.name_var = None
        self._pending_render = None
        self._suspend_traces = False
        self._swatches = {}
        self.shock_widgets = {}
        self._shock_param_labels = {}
        self._pending_scroll_sync = None

        self._build_sidebar(self)
        self._build_plot_area(self)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        self.plot_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        for e in self.entries:
            self.series_by_model[e.key].append(self._new_series(e))

        if self.entries:
            self._select_quietly(self.model_tree, self.entries[0].key)
        self.on_model_change()
        sv_ttk.set_theme("dark")

    def px(self, logical):
        """Accounting for dpi scaling"""
        return round(logical * self._scale)

    def _scale_fonts(self):
        """Rescales the named fonts that are sized in pixels"""
        for name in tkfont.names(self):
            try:
                font = tkfont.nametofont(name, self)
            except tk.TclError:
                continue
            size = font.cget("size")
            if size >= 0:
                continue  # point-sized; Tkinter already scales it
            base = self._font_bases.setdefault(name, size)
            font.configure(size=round(base * self._scale))

    #################################################################
    ###                          Layout                           ###
    #################################################################

    def _build_sidebar(self, parent):
        bar = ttk.Frame(parent, padding=self.px(SIDEBAR_PADDING), width=self.px(SIDEBAR_WIDTH))
        self.sidebar = bar

        ttk.Label(bar, text="Model", font=("", 10, "bold")).pack(anchor="w")
        self.model_tree = ttk.Treeview(
            bar,
            show="tree",
            height=max(len(self.entries), 2),
            selectmode="browse",
        )
        self.model_tree.column("#0", width=self.px(SIDEBAR_INNER), anchor="w")
        for e in self.entries:
            self.model_tree.insert("", tk.END, iid=e.key, text=e.title)
        self.model_tree.pack(fill=tk.X, pady=(2, 10))
        self.model_tree.bind("<<TreeviewSelect>>", lambda x: self.on_model_change())

        ttk.Label(bar, text="View", font=("", 10, "bold")).pack(anchor="w")
        self.view_var = tk.StringVar()
        self.view_frame = ttk.Frame(bar)
        self.view_frame.pack(fill=tk.X, pady=(2, 10))

        ttk.Label(bar, text="Lines", font=("", 10, "bold")).pack(anchor="w")
        self.hint = ttk.Label(
            bar,
            text="click ✓ or double-click a line to show / hide",
            wraplength=self.px(SIDEBAR_INNER),
        )
        self.hint.pack(anchor="w")

        series_box = ttk.Frame(bar)
        series_box.pack(fill=tk.X, pady=(2, 4))
        self.series_tree = ttk.Treeview(
            series_box,
            columns=("name", "shown"),
            show="tree headings",
            height=8,
            selectmode="browse",
            style=SWATCH_STYLE,
        )
        self.series_tree.heading("#0", text="")
        self.series_tree.heading("name", text="Line")
        self.series_tree.heading("shown", text="Shown")
        self.series_tree.column("#0", width=self.px(SWATCH_COL_WIDTH), stretch=False, anchor="center")
        self.series_tree.column(
            "name",
            width=self.px(SIDEBAR_INNER - SWATCH_COL_WIDTH - SHOWN_COL_WIDTH - SIDEBAR_PADDING),
            anchor="w",
        )
        self.series_tree.column(
            "shown",
            width=self.px(SHOWN_COL_WIDTH),
            minwidth=self.px(SHOWN_COL_WIDTH),
            stretch=False,
            anchor="center",
        )

        self.series_scroll = ttk.Scrollbar(series_box, orient=tk.VERTICAL, command=self.series_tree.yview)
        self.series_tree.configure(yscrollcommand=self.series_scroll.set)
        self.series_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.series_tree.bind("<<TreeviewSelect>>", lambda x: self.on_series_change())
        self.series_tree.bind("<Button-1>", self._on_series_click)
        self.series_tree.bind("<Double-Button-1>", self._on_series_double_click)

        buttons = ttk.Frame(bar)
        buttons.pack(fill=tk.X, pady=(0, 10))
        for text, command in (
            ("+ Add", self.add_series),
            ("Copy", self.copy_series),
            ("− Remove", self.remove_series),
        ):
            ttk.Button(buttons, text=text, width=9, command=command).pack(side=tk.LEFT, padx=1)

        ttk.Label(bar, text="Parameters", font=("", 10, "bold")).pack(anchor="w")

        # A ttk.Frame can't scroll, so the grid is built inside a canvas
        param_box = ttk.Frame(bar)
        param_box.pack(fill=tk.BOTH, expand=True, pady=(2, 10))
        self.param_canvas = tk.Canvas(param_box, highlightthickness=0, borderwidth=0)
        self.param_scroll = ttk.Scrollbar(param_box, orient=tk.VERTICAL, command=self.param_canvas.yview)
        self.param_canvas.configure(yscrollcommand=self.param_scroll.set)
        self.param_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.param_frame = ttk.Frame(self.param_canvas)
        self._param_window = self.param_canvas.create_window((0, 0), window=self.param_frame, anchor="nw")
        self.param_frame.bind("<Configure>", lambda x: self._schedule_scroll_sync())
        self.param_canvas.bind("<MouseWheel>", self._on_param_wheel)

        self.status = ttk.Label(bar, text="", wraplength=self.px(SIDEBAR_WIDTH))
        self.status.pack(anchor="w", pady=(10, 0))

        bar.bind("<<ThemeChanged>>", lambda x: self._sync_theme_colors())
        self._sync_theme_colors()

    def _build_plot_area(self, parent):
        plot_area = ttk.Frame(parent)
        self.plot_area = plot_area
        self.fig = Figure(figsize=(7, 7))
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_area)
        NavigationToolbar2Tk(self.canvas, plot_area)  # Pan, zoom, save as PNG
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    #################################################################
    ###                     Theme and colours                     ###
    #################################################################

    def _rgb(self, color):
        """Converts any Tkinter colour spec to (r, g, b) floats in 0..1"""
        return tuple(channel / 65535 for channel in self.winfo_rgb(color))

    def _mix(self, color, other, amount):
        """Blends color toward other, 0 leaving it unchanged and 1 replacing it"""
        a, b = self._rgb(color), self._rgb(other)
        return to_hex(tuple(x + (y - x) * amount for x, y in zip(a, b)))

    def _contrasting(self, color, amount):
        """Nudges a colour toward white if it is dark, toward black if it is light"""
        target = "#ffffff" if sum(self._rgb(color)) / 3 < 0.5 else "#000000"
        return self._mix(color, target, amount)

    def _sync_theme_colors(self):
        """Re-derives every colour this app sets by hand from the live theme"""
        style = ttk.Style(self)
        style.layout(f"{SWATCH_STYLE}.Item", SWATCH_ITEM_LAYOUT)  # type: ignore[arg-type]
        self._scale_fonts()
        style.configure("Treeview", rowheight=self.px(ROW_HEIGHT))
        style.configure("Param.TSpinbox", padding=tuple(self.px(p) for p in (6, 1, 20, 2)))

        frame_bg = style.lookup("TFrame", "background") or "#ffffff"
        tree_bg = style.lookup("Treeview", "fieldbackground") or style.lookup("Treeview", "background") or frame_bg
        tree_fg = style.lookup("Treeview", "foreground") or "#000000"
        label_fg = style.lookup("TLabel", "foreground") or tree_fg

        self.param_canvas.configure(background=frame_bg)

        # Rows are uniform; only the selected one is coloured
        selected_bg = self._contrasting(tree_bg, SELECTED_CONTRAST)
        style.map(
            SWATCH_STYLE,
            background=[("selected", selected_bg)],
            foreground=[("selected", self._contrasting(selected_bg, 1.0))],
        )
        self.series_tree.tag_configure("hidden", foreground=self._mix(tree_fg, tree_bg, HIDDEN_FADE))
        muted = self._mix(label_fg, frame_bg, MUTED_FADE)
        self.hint.configure(foreground=muted)
        self.status.configure(foreground=muted)

    #################################################################
    ###                   Resizing and scrolling                  ###
    #################################################################

    def _schedule_scroll_sync(self):
        if self._pending_scroll_sync is None:
            self._pending_scroll_sync = self.after_idle(self._sync_scrollbars)

    def _sync_scrollbars(self):
        self._pending_scroll_sync = None
        self._sync_param_scroll()
        self._sync_series_scroll()

    def _sync_param_scroll(self):
        """Shows the parameter scrollbar only while the grid is taller than the pane"""
        self.param_canvas.configure(scrollregion=self.param_canvas.bbox("all"))
        height = self.param_canvas.winfo_height()
        if height <= 1:
            return
        needed = self.param_frame.winfo_reqheight() > height - self.px(SCROLL_MARGIN)
        if needed and not self.param_scroll.winfo_ismapped():
            self.param_scroll.pack(side=tk.RIGHT, fill=tk.Y, before=self.param_canvas)
        elif not needed:
            if self.param_scroll.winfo_ismapped():
                self.param_scroll.pack_forget()
            self.param_canvas.yview_moveto(0)

    def _sync_series_scroll(self):
        """Shows the line scrollbar only when there are more lines than visible rows"""
        needed = len(self.series_tree.get_children()) > int(self.series_tree.cget("height"))
        if needed and not self.series_scroll.winfo_ismapped():
            self.series_scroll.pack(side=tk.RIGHT, fill=tk.Y, before=self.series_tree)
        elif not needed and self.series_scroll.winfo_ismapped():
            self.series_scroll.pack_forget()

    def _on_param_wheel(self, event):
        """Scrolls the parameter pane, but only when there is something to scroll"""
        if not self.param_scroll.winfo_ismapped():
            return "break"
        self.param_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _bind_param_wheel(self, *widgets):
        """Binds the wheel on each widget, since events go to the one under the pointer"""
        for widget in widgets:
            widget.bind("<MouseWheel>", self._on_param_wheel)

    #################################################################
    ###                    Parameter editor                       ###
    #################################################################

    def _build_param_editor(self, entry):
        """Rebuilds the parameter widgets from the selected model's ParamSpecs"""
        for child in self.param_frame.winfo_children():
            child.destroy()
        self.param_vars = {}
        self.shock_widgets = {}
        self.param_frame.columnconfigure(0, weight=1)  # Labels take spare width
        self.param_frame.columnconfigure(1, weight=0, minsize=self.px(PARAM_VALUE_WIDTH))

        name_label = ttk.Label(self.param_frame, text="Name", wraplength=self.px(MIN_WRAP))
        name_label.grid(row=0, column=0, sticky="w", pady=1)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(self.param_frame, textvariable=self.name_var, width=10)
        name_entry.grid(row=0, column=1, sticky="ew", pady=1)
        self.name_var.trace_add("write", lambda *x: self.on_name_edit())
        self._bind_param_wheel(name_label, name_entry)

        for row, spec in enumerate(entry.params, start=1):
            label = ttk.Label(self.param_frame, text=spec.label, wraplength=self.px(MIN_WRAP))
            label.grid(row=row, column=0, sticky="w", pady=1)
            var = tk.StringVar()
            box = ttk.Spinbox(
                self.param_frame,
                textvariable=var,
                from_=spec.lo,
                to=spec.hi,
                increment=spec.step,
                width=4,
                command=self.schedule_render,  # Arrow clicks
                style="Param.TSpinbox",
            )
            box.grid(row=row, column=1, sticky="e", pady=1, padx=(15, 5))
            var.trace_add("write", lambda *_: self.schedule_render())  # Typing
            self.param_vars[spec.name] = var
            self._bind_param_wheel(label, box)

        view = self.current_view()
        if view is not None and view.wants_shock:
            self._build_shock_editor(entry, row=len(entry.params) + 1)

        self.param_canvas.yview_moveto(0)
        self._schedule_scroll_sync()

    def _build_shock_editor(self, entry, row):
        """Builds the policy editor. Phrasing used: but now <parameter> (increases/decreases) by <amount>"""
        self.shock_widgets = {}
        self._shock_param_labels = {spec.label: spec.name for spec in entry.params}

        ttk.Separator(self.param_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        lead = ttk.Label(self.param_frame, text="but now…")
        lead.grid(row=row + 1, column=0, columnspan=2, sticky="w")
        self._bind_param_wheel(lead)

        combo_width = 18
        parameter = ttk.Combobox(
            self.param_frame,
            values=list(self._shock_param_labels),
            state="readonly",
            width=combo_width,
        )
        parameter.grid(row=row + 2, column=0, columnspan=2, sticky="ew", pady=1)
        parameter.bind("<<ComboboxSelected>>", lambda x: self.schedule_render())

        direction = ttk.Combobox(
            self.param_frame,
            values=list(transition.DIRECTIONS),
            state="readonly",
            width=combo_width,
        )
        direction.grid(row=row + 3, column=0, columnspan=2, sticky="ew", pady=1)
        direction.bind("<<ComboboxSelected>>", lambda x: self.schedule_render())

        self.shock_widgets["parameter"] = parameter
        self.shock_widgets["direction"] = direction
        self._bind_param_wheel(parameter, direction)

        for offset, (field, spec) in enumerate(
            (
                ("amount", AMOUNT_SPEC),
                ("t_shock", transition.T_SHOCK_SPEC),
                ("periods", transition.PERIODS_SPEC),
            ),
            start=row + 4,
        ):
            label = ttk.Label(self.param_frame, text=spec.label)
            label.grid(row=offset, column=0, sticky="w", pady=1)
            var = tk.StringVar()
            box = ttk.Spinbox(
                self.param_frame,
                textvariable=var,
                from_=spec.lo,
                to=spec.hi,
                increment=spec.step,
                width=4,
                command=self.schedule_render,
                style="Param.TSpinbox",
            )
            box.grid(row=offset, column=1, sticky="e", pady=1, padx=(15, 5))
            var.trace_add("write", lambda *_: self.schedule_render())
            self.shock_widgets[field] = var
            self._bind_param_wheel(label, box)

    def _build_view_selector(self, entry):
        """Rebuilds the radio buttons (policy shock vs. regular view) for the selected model"""
        for child in self.view_frame.winfo_children():
            child.destroy()
        views = entry.views()
        if self.view_var.get() not in {v.key for v in views}:
            self.view_var.set(views[0].key)
        for view in views:
            ttk.Radiobutton(
                self.view_frame,
                text=view.label,
                value=view.key,
                variable=self.view_var,
                command=self.on_view_change,
            ).pack(anchor="w")

    def _swatch(self, color):
        """Returns a cached solid colour square for a line's row"""
        # Cached because Tkinter drops any PhotoImage with no Python reference
        if color not in self._swatches:
            size = self.px(SWATCH_SIZE)
            image = tk.PhotoImage(width=size, height=size)
            image.put(color, to=(0, 0, size, size))
            self._swatches[color] = image
        return self._swatches[color]

    def _select_quietly(self, tree, item):
        """Selects a row without letting the resulting event drive a redraw"""
        self._suspend_traces = True
        try:
            tree.selection_set(item)
            tree.focus(item)
        finally:
            self._suspend_traces = False

    #################################################################
    ###                      Current state                        ###
    #################################################################

    def current_entry(self):
        sel = self.model_tree.selection()
        return REGISTRY.get(sel[0]) if sel else None

    def current_view(self):
        entry = self.current_entry()
        if entry is None:
            return None
        wanted = self.view_var.get()
        views = entry.views()
        return next((v for v in views if v.key == wanted), views[0])

    def _selected_index(self):
        """Index into the current model's series list, or None"""
        sel = self.series_tree.selection()
        return int(sel[0]) if sel else None

    def current_series(self):
        entry = self.current_entry()
        index = self._selected_index()
        if entry is None or index is None:
            return None
        lines = self.series_by_model[entry.key]
        return lines[index] if index < len(lines) else None

    #################################################################
    ###                       Editing lines                       ###
    #################################################################

    def _new_series(self, entry, values=None, label=None, shock=None):
        lines = self.series_by_model[entry.key]
        return Series(
            values=dict(values) if values else entry.defaults(),
            label=label or f"Line {len(lines) + 1}",
            color=to_hex(next(self._color_cycles[entry.key])),  # to_hex to ensure it reads the color correctly
            shock=replace(shock) if shock else Shock(parameter=_default_instrument(entry), amount=AMOUNT_SPEC.default),
        )

    def add_series(self):
        entry = self.current_entry()
        if entry is None:
            return
        self.series_by_model[entry.key].append(self._new_series(entry))
        self._refresh_series_list(select=len(self.series_by_model[entry.key]) - 1)
        self.on_series_change()

    def copy_series(self):
        entry, source = self.current_entry(), self.current_series()
        if entry is None or source is None:
            return
        lines = self.series_by_model[entry.key]
        lines.append(
            self._new_series(
                entry,
                values=source.values,
                label=f"{source.label} copy",
                shock=source.shock,
            )
        )
        self._refresh_series_list(select=len(lines) - 1)
        self.on_series_change()

    def remove_series(self):
        entry = self.current_entry()
        index = self._selected_index()
        if entry is None or index is None:
            return
        lines = self.series_by_model[entry.key]
        del lines[index]
        self._refresh_series_list(select=min(index, len(lines) - 1) if lines else None)
        self.on_series_change()

    def _toggle_index(self, index):
        entry = self.current_entry()
        if entry is None:
            return
        lines = self.series_by_model[entry.key]
        if not 0 <= index < len(lines):
            return
        lines[index].visible = not lines[index].visible
        self._refresh_series_list(select=index)
        self.render()

    def on_name_edit(self):
        if self._suspend_traces:
            return
        series = self.current_series()
        if series is None:
            return
        series.label = self.name_var.get() or "Line"
        self._refresh_series_list(select=self._selected_index())
        self.schedule_render()

    def _refresh_series_list(self, select=None):
        entry = self.current_entry()
        if entry is None:
            return
        self.series_tree.delete(*self.series_tree.get_children())
        lines = self.series_by_model[entry.key]
        for i, s in enumerate(lines):
            tags = [] if s.visible else ["hidden"]
            # The list index is the row id, so a selection is an index already
            self.series_tree.insert(
                "",
                tk.END,
                iid=str(i),
                image=self._swatch(s.color),
                values=(s.label, "✓" if s.visible else "✗"),
                tags=tuple(tags),
            )
        if select is not None and 0 <= select < len(lines):
            self._select_quietly(self.series_tree, str(select))
        self._sync_series_scroll()

    #################################################################
    ###                         Events                            ###
    #################################################################

    def _on_series_click(self, event):
        """Toggles a line when the click lands in the Shown column"""
        region = self.series_tree.identify_region(event.x, event.y)
        if region == "separator":
            return "break"  # Swallowing the press is what fixes the columns
        if region != "cell":
            return None
        if self.series_tree.identify_column(event.x) != SHOWN_COLUMN:
            return None
        item = self.series_tree.identify_row(event.y)
        if not item:
            return None
        self._toggle_index(int(item))
        return "break"

    def _on_series_double_click(self, event):
        """Toggles a line on a double-click anywhere but the Shown column"""
        if self.series_tree.identify_region(event.x, event.y) == "separator":
            return "break"
        # The first click in the Shown column has already toggled the line
        if self.series_tree.identify_column(event.x) == SHOWN_COLUMN:
            return "break"
        item = self.series_tree.identify_row(event.y)
        if item:
            self._toggle_index(int(item))
        return None

    def on_model_change(self):
        if self._suspend_traces:
            return
        entry = self.current_entry()
        if entry is None:
            return
        self._build_view_selector(entry)
        self._build_param_editor(entry)
        self._refresh_series_list(select=0)
        self.on_series_change()

    def on_view_change(self):
        """Rebuilds the editor, since only one view needs the policy sentence"""
        entry = self.current_entry()
        if entry is None:
            return
        self._build_param_editor(entry)
        self.on_series_change()

    def on_series_change(self):
        if self._suspend_traces:
            return
        self._populate_params()
        self.render()

    def _populate_params(self):
        """Pushes the selected series into the widgets"""
        # Traces are suspended so setting a var does not write straight back
        series = self.current_series()
        if series is None:
            return
        self._suspend_traces = True
        try:
            self.name_var.set(series.label)
            for name, var in self.param_vars.items():
                var.set(f"{series.values.get(name, 0.0):g}")
            self._populate_shock(series)
        finally:
            self._suspend_traces = False

    def _populate_shock(self, series):
        """Pushes the selected series' policy into the sentence widgets"""
        if not self.shock_widgets:
            return
        shock = series.shock
        labels = self._shock_param_labels
        chosen = next((label for label, name in labels.items() if name == shock.parameter), "")
        self.shock_widgets["parameter"].set(chosen)
        self.shock_widgets["direction"].set(shock.direction)
        for field in ("amount", "t_shock", "periods"):
            self.shock_widgets[field].set(f"{getattr(shock, field):g}")

    #################################################################
    ###                          Drawing                          ###
    #################################################################

    def schedule_render(self):
        """Waits a moment before executing changes when buttons are spammed like I know you barbarians are doing"""
        if self._suspend_traces:
            return
        if self._pending_render is not None:
            self.after_cancel(self._pending_render)
        self._pending_render = self.after(150, self.commit_and_render)

    def commit_and_render(self):
        """Reads the widgets into the selected series, then redraws"""
        self._pending_render = None
        entry, series = self.current_entry(), self.current_series()
        if entry is None or series is None:
            self.render()
            return

        clamped = []
        for spec in entry.params:
            raw = self.param_vars[spec.name].get().strip()
            try:
                value = float(raw)
            except ValueError:
                continue
            series.values[spec.name] = spec.clamp(value)
            if series.values[spec.name] != value:
                clamped.append(spec.name)

        self._commit_shock(series)

        note = f"clamped {', '.join(clamped)} to range" if clamped else None
        self.render(note=note)

    def _commit_shock(self, series):
        """Reads the policy sentence back into the selected series"""
        if not self.shock_widgets:
            return
        shock = series.shock
        shock.parameter = self._shock_param_labels.get(self.shock_widgets["parameter"].get(), "")
        direction = self.shock_widgets["direction"].get()
        if direction in transition.DIRECTIONS:
            shock.direction = direction
        for field, spec in (
            ("amount", AMOUNT_SPEC),
            ("t_shock", transition.T_SHOCK_SPEC),
            ("periods", transition.PERIODS_SPEC),
        ):
            raw = self.shock_widgets[field].get().strip()
            try:
                setattr(shock, field, spec.clamp(float(raw)))
            except ValueError:
                continue

    def render(self, note=None):
        """Draws the selected view and reports the result in the status line"""
        entry = self.current_entry()
        view = self.current_view()
        if entry is None or view is None:
            return
        lines = self.series_by_model[entry.key]
        self.fig.clear()  # Prevents plots stacking up
        try:
            view.run(self.fig, lines)
            if len(self.fig.axes) > 1:
                self.fig.suptitle(
                    entry.title,
                    color=diagram.TEXT_COLOR,
                    fontsize=diagram.TITLE_SIZE,
                )
            elif self.fig.axes:
                self.fig.axes[0].set_title(
                    entry.title,
                    color=diagram.TEXT_COLOR,
                    fontsize=diagram.TITLE_SIZE,
                    pad=12,
                )
            shown = sum(1 for s in lines if s.visible)
            message = f"{shown}/{len(lines)} lines shown"
            self.status.config(text=f"{message} — {note}" if note else message)
        except Exception as exc:  # A bad parameterization should not kill the app
            self.fig.clear()
            self.fig.text(0.5, 0.5, f"Error:\n{exc}", ha="center", va="center", fontsize=10)
            self.status.config(text=f"render failed: {exc}")
        self.canvas.draw_idle()
        sv_ttk.set_theme("dark")


if __name__ == "__main__":
    App().mainloop()
