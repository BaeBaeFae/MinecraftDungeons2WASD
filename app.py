"""Dungeons Input Studio: portable Windows companion, supported-build beta."""
import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import queue
import threading
import time
import traceback
from model import KEYS, PRESETS, Settings, VERSION
from guidance import guide, classify_error, STEPS

DATA = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'DungeonsInputStudio'


from worker import Worker


def probe(path):
    """Exercise discovery and configuration planning with a read-only process handle."""
    from engine import Engine
    from winmem import Process, find_game
    found = find_game()
    if not found:
        raise RuntimeError('Game not running.')
    process = Process(found, writable=False)
    try:
        engine = Engine(process, Settings())
        changes = []
        class Preview:
            entries = {}
            def set(self, address, value, guard, key=False, original=None):
                if not guard():
                    raise RuntimeError('Read-only preview guard failed.')
                changes.append({'size': len(value), 'key': key, 'already_applied': process.read(address, len(value)) == value})
            def prune(self):
                pass
        engine.journal = Preview()
        engine.sync()
        engine.tick(1/120)
        report = engine.diagnostics()
        report.update({'read_only': True, 'planned_operations': changes,
                       'discovered_classes': {k: len(v) for k, v in engine.u.index.items()}})
        Path(path).write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        process.close()


def gui(smoke=None, start_immediately=False):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import ctypes
    from winmem import k
    mutex_name = 'Local\\DungeonsInputStudio-UI-Smoke' if smoke else 'Local\\DungeonsInputStudio-0.1'
    mutex = k.CreateMutexW(None, False, mutex_name)
    if ctypes.get_last_error() == 183:
        messagebox.showinfo('Already running', 'Dungeons Input Studio is already open.')
        k.CloseHandle(mutex)
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    root.title('Dungeons Input Studio')
    root.geometry('860x920')
    root.minsize(800, 760)
    root.configure(bg='#111820')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 10), background='#18222d', foreground='#e5edf4')
    style.configure('TFrame', background='#111820')
    style.configure('TLabelframe', background='#111820', bordercolor='#32404f')
    style.configure('TLabelframe.Label', background='#111820', foreground='#8fddc9', font=('Segoe UI', 11, 'bold'))
    style.configure('TLabel', background='#111820')
    style.configure('TCheckbutton', background='#111820')
    style.map('TCheckbutton', background=[('active', '#111820')])
    style.configure('TButton', padding=(12, 8), background='#273848', borderwidth=0)
    style.map('TButton', background=[('active', '#3a5368')])
    style.configure('Accent.TButton', background='#276e60', foreground='white')
    style.map('Accent.TButton', background=[('active', '#338a78')])
    style.configure('TCombobox', fieldbackground='#20303e', foreground='#eef5fa', arrowsize=15)
    style.map('TCombobox', fieldbackground=[('readonly', '#20303e')], foreground=[('readonly', '#eef5fa')])
    style.configure('TSpinbox', fieldbackground='#20303e', foreground='#eef5fa',
                    background='#273848', arrowcolor='#eef5fa', insertcolor='#eef5fa',
                    selectbackground='#276e60', selectforeground='#ffffff',
                    bordercolor='#526879', lightcolor='#526879', darkcolor='#526879',
                    padding=4, arrowsize=14)
    style.map('TSpinbox',
              fieldbackground=[('disabled', '#18222d'), ('!disabled', '#20303e')],
              foreground=[('disabled', '#91a6b8'), ('!disabled', '#eef5fa')],
              background=[('active', '#3a5368'), ('!active', '#273848')],
              arrowcolor=[('disabled', '#91a6b8'), ('!disabled', '#eef5fa')],
              bordercolor=[('focus', '#8fddc9'), ('!focus', '#526879')])
    style.configure('TNotebook', background='#111820', borderwidth=0)
    style.configure('TNotebook.Tab', padding=(18, 9), background='#1b2935')
    style.map('TNotebook.Tab', background=[('selected', '#304555')])
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='DUNGEONS INPUT STUDIO', font=('Segoe UI', 21, 'bold')).pack(anchor='w')
    ttk.Label(frame, text=f'WASD, precise clicks, smoother turning  ·  {VERSION}', foreground='#91a6b8').pack(anchor='w', pady=(4, 16))
    status = tk.StringVar()
    detail_text = tk.StringVar()
    next_text = tk.StringVar()
    pending_text = tk.StringVar()
    status_card = tk.Frame(frame, bg='#172936', padx=16, pady=13, highlightthickness=1, highlightbackground='#385367')
    status_card.pack(fill='x', pady=(0, 12))
    status_title = tk.Label(status_card, textvariable=status, bg='#172936', fg='#c9e8ff',
                            font=('Segoe UI', 14, 'bold'), anchor='w', justify='left', wraplength=745)
    status_title.pack(fill='x')
    status_detail = tk.Label(status_card, textvariable=detail_text, bg='#172936', fg='#d2dde6',
                             font=('Segoe UI', 10), anchor='w', justify='left', wraplength=745)
    status_detail.pack(fill='x', pady=(5, 7))
    status_next = tk.Label(status_card, textvariable=next_text, bg='#172936', fg='#c9e8ff',
                           font=('Segoe UI', 10, 'bold'), anchor='w', justify='left', wraplength=745)
    status_next.pack(fill='x')
    ttk.Label(frame, textvariable=pending_text, foreground='#ffd28a', wraplength=745).pack(fill='x', pady=(0, 6))
    actions = ttk.Frame(frame)
    actions.pack(fill='x', pady=(0, 18))
    events = queue.Queue()
    worker = Worker(events)
    worker.start()
    variables = {}
    settings = Settings()
    load_error = None
    try:
        if (DATA/'settings.json').exists():
            settings = Settings.load(DATA/'settings.json')
    except Exception as exc:
        load_error = f'Saved profile could not be loaded: {exc}. Defaults are shown.'
    for key, value in asdict(settings).items():
        variables[key] = tk.BooleanVar(value=value) if type(value) is bool else tk.StringVar(value=str(value))
    closing = False
    active = False
    current_guide = guide('idle')
    applied_values = None

    def collect():
        values = {k: v.get() for k, v in variables.items()}
        for key in ('maximum', 'acceleration', 'deceleration', 'ease_out', 'slam_delay'):
            values[key] = float(values[key])
        return Settings(**values).validate()

    def update_vars(value):
        for key, val in asdict(value).items():
            variables[key].set(val)

    def apply(start=False):
        nonlocal active, worker
        try:
            value = collect()
            value.save(DATA/'settings.json')
            if not worker.is_alive():
                worker = Worker(events)
                worker.start()
                active = False
            command = 'start' if start and not active else 'settings'
            worker.commands.put((command, value))
            if start:
                active = True
                render_guide(guide('connecting'))
            elif not active:
                pending_text.set('Profile saved. Complete the setup steps to apply it to the game.')
        except Exception as exc:
            messagebox.showerror('Check your settings', str(exc), parent=root)

    def stop():
        nonlocal active
        active = False
        worker.commands.put(('stop', None))
        status.set('Restoring owned changes…')
        next_text.set('Please wait before closing the companion.')

    def restore_originals():
        nonlocal worker
        if not worker.is_alive():
            worker = Worker(events)
            worker.start()
        worker.commands.put(('restore', None))
        status.set('Restoring your original controls…')

    start_button = ttk.Button(actions, text='2 · Start companion', style='Accent.TButton', command=lambda: apply(True))
    start_button.pack(side='left')
    apply_button = ttk.Button(actions, text='3 · Apply settings', command=apply)
    apply_button.pack(side='left', padx=8)
    stop_button = ttk.Button(actions, text='Restore originals', command=restore_originals)
    stop_button.pack(side='right')
    notebook = ttk.Notebook(frame)
    notebook.pack(fill='both', expand=True)
    pages = {}
    def page(title):
        shell = ttk.Frame(notebook)
        canvas = tk.Canvas(shell, bg='#111820', highlightthickness=0)
        scrollbar = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        body = ttk.Frame(canvas, padding=18)
        window = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
        notebook.add(shell, text=title)
        pages[str(shell)] = (canvas, body)
        return body
    setup = page('Setup')
    control = page('Controls')
    turning = page('Turning')
    help_tab = page('Setup & diagnostics')
    def scroll_page(event):
        if event.widget.winfo_class() not in ('TSpinbox', 'TCombobox', 'TScale', 'Text'):
            canvas, body = pages[notebook.select()]
            canvas.yview_scroll(-int(event.delta/120), 'units')
    root.bind('<MouseWheel>', scroll_page)
    process_row = ttk.LabelFrame(setup, text='Game process', padding=10)
    process_row.pack(fill='x', pady=(0, 14))
    process_choice = tk.StringVar(value='Auto detect')
    process_choices = {'Auto detect': None}
    process_list = []
    show_all = tk.BooleanVar(value=False)
    process_combo = ttk.Combobox(process_row, textvariable=process_choice, values=('Auto detect',), state='readonly', width=47)
    process_combo.pack(side='left', fill='x', expand=True)
    def refresh_processes():
        worker.commands.put(('processes', None))
    def show_processes():
        process_choices.clear()
        process_choices['Auto detect'] = None
        for item in process_list:
            if show_all.get() or 'dungeons' in item['name'].lower():
                process_choices[f"{item['pid']} — {item['name']}"] = item['pid']
        process_combo.configure(values=tuple(process_choices))
    def select_process(event=None):
        worker.commands.put(('select_process', process_choices.get(process_choice.get())))
    process_combo.bind('<<ComboboxSelected>>', select_process)
    ttk.Button(process_row, text='Refresh', command=refresh_processes).pack(side='left', padx=8)
    ttk.Checkbutton(setup, text='Show all processes (when the game is missing from the list)',
                    variable=show_all, command=show_processes).pack(anchor='w', pady=(0, 6))
    ttk.Label(setup, text='Refresh, select the actual game process, then Start companion. Manual selection still verifies the supported build. Restore originals before switching processes.',
              foreground='#91a6b8', wraplength=685).pack(anchor='w', pady=(0, 14))
    ttk.Label(setup, text='A clear path from setup to play', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
    ttk.Label(setup, text='First setup may need title. A prepared character can reconnect here without leaving gameplay.',
              foreground='#91a6b8', wraplength=690).pack(anchor='w', pady=(4, 12))
    step_labels = []
    for number, (title, description) in enumerate(STEPS, 1):
        row = ttk.Frame(setup)
        row.pack(fill='x', pady=(0, 14))
        title_label = ttk.Label(row, text=f'{number}.  {title}', font=('Segoe UI', 11, 'bold'))
        title_label.pack(anchor='w')
        ttk.Label(row, text=description, foreground='#a8bac8', wraplength=685).pack(anchor='w', padx=24, pady=(3, 0))
        step_labels.append(title_label)
    ttk.Separator(setup).pack(fill='x', pady=(0, 14))
    ttk.Label(setup, text='Live verification', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
    checks_text = tk.StringVar(value='No game checks yet. Start the companion from the title screen.')
    ttk.Label(setup, textvariable=checks_text, wraplength=690, foreground='#a8bac8', justify='left').pack(anchor='w', pady=(6, 12))
    ttk.Label(setup, text='Having trouble? The status panel above shows the next step. You do not need to open diagnostics to see setup errors.',
              wraplength=690, foreground='#91a6b8').pack(anchor='w')

    def render_guide(value):
        nonlocal current_guide, active
        current_guide = value
        active = value.can_stop
        process_combo.configure(state='readonly' if value.stage in (
            'idle', 'waiting_game', 'select_process', 'stopped', 'error', 'unsupported', 'restore_warning') else 'disabled')
        colors = {'info': ('#172936', '#c9e8ff'), 'waiting': ('#292719', '#ffe3a1'),
                  'warning': ('#332817', '#ffd28a'), 'error': ('#361e25', '#ffb4bb'),
                  'success': ('#17302a', '#9ae9ca')}
        bg, fg = colors[value.tone]
        status_card.configure(bg=bg, highlightbackground=fg)
        status_title.configure(bg=bg, fg=fg)
        status_detail.configure(bg=bg)
        status_next.configure(bg=bg, fg=fg)
        status.set(value.title)
        detail_text.set(value.detail)
        next_text.set('Next: ' + value.next_action)
        start_button.configure(text='Retry connection' if value.stage in ('error', 'unsupported', 'restore_warning') else '2 · Start companion')
        start_button.state(['!disabled'] if value.can_start else ['disabled'])
        apply_button.state(['!disabled'] if value.can_apply else ['disabled'])
        apply_button.configure(style='Accent.TButton' if value.stage == 'apply' else 'TButton')
        stop_button.state(['disabled'] if closing else ['!disabled'])
        for index, label in enumerate(step_labels):
            done = index < value.progress
            current = index == value.progress
            prefix = 'DONE' if done else 'NEXT' if current else str(index+1)
            label.configure(text=f'{prefix}   {STEPS[index][0]}', foreground='#8fddc9' if done else fg if current else '#8b9ba9')
        if value.checks:
            checks_text.set('\n'.join('• '+check for check in value.checks))
        elif value.stage in ('apply', 'load_character'):
            checks_text.set('• Supported game version verified\n• Title screen detected\n• '+('Waiting for Apply settings' if value.stage == 'apply' else 'Settings applied; waiting for a gameplay character'))
        else:
            checks_text.set('Gameplay settings are not yet verified for the current character.')

    def check(parent, key, title, note):
        ttk.Checkbutton(parent, text=title, variable=variables[key]).pack(anchor='w', pady=(5, 2))
        ttk.Label(parent, text=note, wraplength=640, foreground='#91a6b8').pack(anchor='w', padx=23, pady=(0, 12))

    check(control, 'wasd', 'Enable keyboard movement', 'Native movement. Rebind any conflicting game controls when prompted.')
    grid = ttk.Frame(control)
    grid.pack(fill='x', padx=23, pady=(0, 18))
    for index, (key, label) in enumerate([('forward', 'Forward'), ('left', 'Left'), ('back', 'Back'), ('right', 'Right')]):
        ttk.Label(grid, text=label).grid(row=0, column=index, sticky='w', padx=(0, 24))
        ttk.Combobox(grid, textvariable=variables[key], values=KEYS, state='readonly', width=8).grid(row=1, column=index, padx=(0, 24), pady=5)
    check(control, 'native_interactions', 'Native interaction mode (revive workaround)',
          'Restores the original attack / interact / click-to-approach behavior while keeping WASD and turning. Enable and Apply before attempting a revive. Click movement returns in this mode; co-op is not yet validated.')
    check(control, 'attack_in_place', 'Attack in place with your primary button', 'Pairs Root / Stand Still with your primary action. Shift is free for another binding.')
    check(control, 'block_ground_move', 'Disable clicking the ground to move', 'Blocks both movement while holding the button and movement after release.')
    check(control, 'block_interaction_approach', 'Walk to interactions yourself', 'Clicking a distant chest or NPC will not walk you there. Move into range to interact.')
    check(control, 'jump_slam', 'Jump + hold left-click to slam (beta)',
          'Uses your in-game Jump Slam binding once per airborne movement. Your manual binding keeps working. Enable, then Apply settings.')
    slam_row = ttk.Frame(control)
    slam_row.pack(fill='x', padx=23, pady=(0, 10))
    from slam import BINDINGS
    ttk.Label(slam_row, text='Jump Slam binding').pack(side='left', padx=(0, 12))
    ttk.Combobox(slam_row, textvariable=variables['slam_binding'], values=BINDINGS,
                 state='readonly', width=24).pack(side='left')
    ttk.Label(control, text='Auto detects the game binding. Mouse side 1 = ThumbMouseButton; side 2 = ThumbMouseButton2. A selected key must already be bound to Jump Slam in the game.',
              wraplength=640, foreground='#91a6b8').pack(anchor='w', padx=23, pady=(0, 10))
    delay_row = ttk.Frame(control)
    delay_row.pack(fill='x', padx=23, pady=(0, 14))
    ttk.Label(delay_row, text='Minimum airborne time before slam (ms)').pack(side='left')
    ttk.Spinbox(delay_row, from_=0, to=500, increment=10, textvariable=variables['slam_delay'], width=8).pack(side='right')
    ttk.Label(control, text='Other buttons: remap them in the game. Keep this companion running to maintain the chosen input behavior.',
              wraplength=640, foreground='#91a6b8').pack(anchor='w', pady=(10, 0))

    preset_line = ttk.Frame(turning)
    preset_line.pack(fill='x', pady=(0, 14))
    ttk.Label(preset_line, text='Feel preset').pack(side='left', padx=(0, 12))
    preset_var = tk.StringVar(value='Responsive')
    preset = ttk.Combobox(preset_line, textvariable=preset_var, values=tuple(PRESETS), state='readonly', width=20)
    preset.pack(side='left')
    def choose_preset(event=None):
        value = PRESETS[preset_var.get()]
        for key in ('smooth', 'maximum', 'acceleration', 'deceleration', 'ease_out'):
            variables[key].set(getattr(value, key))
    preset.bind('<<ComboboxSelected>>', choose_preset)
    check(turning, 'smooth', 'Smooth turning', 'Ramp turn speed up, then ease down near the desired direction. Off uses a constant speed limit.')
    for key, title, units, low, high, note in [
        ('maximum', 'Maximum turn speed', 'degrees / second', 90, 1800, 'Higher values make large turns faster.'),
        ('acceleration', 'Acceleration', 'degrees / second²', 500, 20000, 'Higher values reach full turn speed sooner.'),
        ('deceleration', 'Deceleration', 'degrees / second²', 500, 20000, 'Higher values slow the turn down more quickly.'),
        ('ease_out', 'Near-target response', '4–40', 4, 40, 'Lower values soften the finish. Higher values feel more direct.'),
    ]:
        row = ttk.Frame(turning)
        row.pack(fill='x', pady=(8, 0))
        ttk.Label(row, text=title, font=('Segoe UI', 11, 'bold')).pack(side='left')
        ttk.Spinbox(row, from_=low, to=high, increment=1 if key == 'ease_out' else 50,
                    textvariable=variables[key], width=9).pack(side='right')
        ttk.Label(row, text=units, foreground='#91a6b8').pack(side='right', padx=12)
        ttk.Scale(turning, from_=low, to=high, variable=variables[key],
                  command=lambda value, k=key: variables[k].set(str(round(float(value))))).pack(fill='x', pady=4)
        ttk.Label(turning, text=note, foreground='#91a6b8').pack(anchor='w', pady=(0, 8))

    instructions = (
        '1. Launch the game and stay at its title screen.\n'
        '2. Click Start companion and wait for title-screen detection.\n'
        '3. Click Apply settings, then load your character in the game.\n'
        '4. Wait for the green Working status. Rebind any reported conflicts.\n\n'
        'Connection failures save a local, redacted report automatically. After an issue, use Save diagnostics to include the recent error history, controller class, input tree, and retry attempts. No upload occurs.\n\n'
        'Supported: Windows x64, the verified Steam executable for build 1.1.1.0. '
        'Other game builds are rejected. This beta has been tested on one PC in single-player; '
        'a second PC has also been reported working by the user. Stop & restore before joining or hosting multiplayer.\n\n'
        'Changes are made to live data. No game executable or asset files are modified. '
        'The in-memory Root binding may be saved by the game if you save controls; '
        'Stop & restore first if you want its original binding. A forced app close can leave '
        'runtime changes until the game restarts. The global WASD feature is off at title.'
    )
    ttk.Label(help_tab, text='Original controls are recorded before changes. Restore originals applies the saved values to the current game immediately; no title-screen step is required for restoration. Backups are stored in: ' + str(DATA/'backups'), wraplength=640, foreground='#8fddc9').pack(anchor='w', pady=(0, 12))
    ttk.Label(help_tab, text=instructions, wraplength=640, justify='left').pack(anchor='w')
    log = tk.Text(help_tab, height=8, bg='#0c1218', fg='#a9bbca', insertbackground='white',
                  relief='flat', font=('Consolas', 9), wrap='word')
    log.pack(fill='both', expand=True, pady=14)
    log.insert('end', 'Diagnostics stay on this PC. No telemetry or network connection.\n')
    if load_error:
        log.insert('end', load_error + '\n')
    bottom = ttk.Frame(frame)
    bottom.pack(fill='x', pady=(16, 0))
    def export():
        path = filedialog.asksaveasfilename(parent=root, defaultextension='.json', initialfile='my-dungeons-profile.json', filetypes=[('Profile', '*.json')])
        if path:
            try:
                collect().save(path)
            except Exception as exc:
                messagebox.showerror('Export failed', str(exc), parent=root)
    def import_profile():
        path = filedialog.askopenfilename(parent=root, filetypes=[('Profile', '*.json')])
        if path:
            try:
                update_vars(Settings.load(path))
                pending_text.set('Profile imported — these changes are not applied yet.')
            except Exception as exc:
                messagebox.showerror('Import failed', str(exc), parent=root)
    def diagnostics():
        path = filedialog.asksaveasfilename(parent=root, defaultextension='.json', initialfile='dungeons-diagnostics.json', filetypes=[('Diagnostics', '*.json')])
        if path:
            worker.commands.put(('diagnostics', path))
    ttk.Button(bottom, text='Import profile', command=import_profile).pack(side='left')
    ttk.Button(bottom, text='Export profile', command=export).pack(side='left', padx=8)
    ttk.Button(bottom, text='Save diagnostics', command=diagnostics).pack(side='right')
    ttk.Label(frame, text='Independent community tool. Not affiliated with Mojang or Microsoft.', foreground='#74899b').pack(anchor='w', pady=(12, 0))

    def close():
        nonlocal closing, worker
        if closing:
            return
        answer = True if smoke else messagebox.askyesnocancel(
            'Restore your original controls?',
            'Yes — Restore original controls and close.\n'
            'No — Close without reverting bindings and click settings.\n'
            'Cancel — Keep the companion open.\n\n'
            'Without reverting, originals stay backed up for this game session. '
            'Smoothing and Jump Slam assist stop when the app closes, and the title compatibility flag is cleared.',
            parent=root)
        if answer is None:
            return
        if not worker.is_alive():
            worker = Worker(events)
            worker.start()
        closing = True
        worker.commands.put(('close' if answer and not smoke else 'close_keep', None))
        status.set('Restoring changes before closing…' if answer else 'Saving originals and closing…')
        if not worker.is_alive():
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    def changed(*args):
        try:
            same = applied_values is not None and asdict(collect()) == applied_values
        except (ValueError, TypeError):
            same = False
        pending_text.set('' if same else 'Changes not applied — click Apply settings when that step is available.')
    for variable in variables.values():
        variable.trace_add('write', changed)
    render_guide(guide('idle'))
    def pump():
        nonlocal active, applied_values, closing, process_list
        while True:
            try:
                kind, value = events.get_nowait()
            except queue.Empty:
                break
            if kind == 'guide':
                render_guide(value)
            elif kind == 'processes':
                process_list = value
                show_processes()
            elif kind == 'selection_reset':
                process_choice.set('Auto detect')
            elif kind == 'notice':
                log.insert('end', value)
            elif kind == 'applied':
                applied_values = value
                changed()
            elif kind in ('status', 'fatal'):
                status.set(value)
                log.insert('end', value+'\n')
                if kind == 'fatal':
                    active = False
            elif kind == 'log':
                log.insert('end', value+'\n')
            elif kind == 'diagnostics':
                path, report = value
                try:
                    Path(path).write_text(json.dumps(report, indent=2), encoding='utf-8')
                except Exception as exc:
                    messagebox.showerror('Could not save diagnostics', str(exc), parent=root)
            elif kind == 'close_failed':
                closing = False
                messagebox.showwarning('Restoration needs attention', value + '\nThe companion has stayed open. Retry Restore original controls or restart the game.', parent=root)
            elif kind == 'closed' and closing:
                root.destroy()
                return
            if int(log.index('end-1c').split('.')[0]) > 250:
                log.delete('1.0', '50.0')
            log.see('end')
        root.after(100, pump)
    root.after(100, pump)
    if start_immediately and not smoke:
        root.after(300, lambda: apply(True))
    if smoke:
        def smoke_test():
            turning_shell = next(key for key, pair in pages.items() if pair[1] is turning)
            notebook.select(turning_shell)
            root.update_idletasks()
            def luminance(color):
                channels = [v / 65535 for v in root.winfo_rgb(color)]
                linear = [v / 12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in channels]
                return sum(v*w for v, w in zip(linear, (.2126, .7152, .0722)))
            contrast = {}
            for state in [(), ('focus',), ('active',), ('readonly',), ('disabled',)]:
                fg = style.lookup('TSpinbox', 'foreground', state)
                bg = style.lookup('TSpinbox', 'fieldbackground', state)
                a, b = sorted((luminance(fg), luminance(bg)))
                ratio = (b+.05)/(a+.05)
                assert ratio >= 4.5, (state, fg, bg, ratio)
                contrast['+'.join(state) or 'normal'] = {'foreground': fg, 'background': bg, 'ratio': round(ratio, 2)}
            scenarios = {}
            for stage in ('idle', 'waiting_game', 'connecting', 'apply', 'load_character', 'active',
                          'resume', 'unknown_screen', 'select_process', 'return_title', 'needs_reload', 'conflict', 'assist_warning', 'recovering', 'unsupported', 'error', 'stopped'):
                render_guide(guide(stage))
                root.update_idletasks()
                scenarios[stage] = {'title': status.get(), 'next': next_text.get(),
                                    'start_enabled': not start_button.instate(['disabled']),
                                    'apply_enabled': not apply_button.instate(['disabled'])}
            report = {'tabs': len(notebook.tabs()), 'settings': asdict(collect()),
                      'window': [root.winfo_width(), root.winfo_height()],
                      'requested': [frame.winfo_reqwidth(), frame.winfo_reqheight()], 'status': status.get(),
                      'turning_value_contrast': contrast, 'guided_states': scenarios}
            Path(smoke).write_text(json.dumps(report, indent=2), encoding='utf-8')
            close()
        root.after(700, smoke_test)
    root.mainloop()
    if worker.is_alive():
        worker.commands.put(('close', None))
        worker.join(timeout=10)
    k.CloseHandle(mutex)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', help='Write a read-only compatibility/discovery report; do not modify the game.')
    parser.add_argument('--ui-smoke', help='Open and structurally check the GUI without attaching to the game.')
    parser.add_argument('--start', action='store_true', help='Start the companion after opening its window.')
    args = parser.parse_args()
    if args.probe:
        probe(args.probe)
    else:
        gui(args.ui_smoke, args.start)
