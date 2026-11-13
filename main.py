from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.utils import get_color_from_hex

# Dark background set kora
Window.clearcolor = get_color_from_hex('#0F172A')

# Android Hardware Control (Flashlight & Battery)
try:
    from jnius import autoclass
    Context = autoclass('android.content.Context')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    BatteryManager = autoclass('android.os.BatteryManager')
    
    activity = PythonActivity.mActivity
    camera_manager = activity.getSystemService(Context.CAMERA_SERVICE)
    camera_id = camera_manager.getCameraIdList()[0]
    battery_manager = activity.getSystemService(Context.BATTERY_SERVICE)
    ANDROID_AVAILABLE = True
except Exception as e:
    ANDROID_AVAILABLE = False


class GlowFlashButton(Widget):
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.is_on = False
        self.glow_radius = 0

        with self.canvas:
            self.glow_color = Color(1, 0.85, 0.2, 0)
            self.glow_circle = Ellipse()

            self.ring_color = Color(0.2, 0.28, 0.4, 1)
            self.ring_circle = Ellipse()

            self.btn_color = Color(0.12, 0.16, 0.23, 1)
            self.btn_circle = Ellipse()

        self.bind(pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        cx, cy = self.center_x, self.center_y
        base_r = min(self.width, self.height) * 0.34

        gr = base_r + self.glow_radius
        self.glow_circle.pos = (cx - gr, cy - gr)
        self.glow_circle.size = (gr * 2, gr * 2)

        rr = base_r + 8
        self.ring_circle.pos = (cx - rr, cy - rr)
        self.ring_circle.size = (rr * 2, rr * 2)

        self.btn_circle.pos = (cx - base_r, cy - base_r)
        self.btn_circle.size = (base_r * 2, base_r * 2)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            cx, cy = self.center_x, self.center_y
            base_r = min(self.width, self.height) * 0.34
            if ((touch.x - cx) ** 2 + (touch.y - cy) ** 2) ** 0.5 <= base_r + 15:
                self.callback()
                return True
        return super().on_touch_down(touch)

    def animate_state(self, state, sos_mode=False):
        self.is_on = state
        Animation.cancel_all(self)
        Animation.cancel_all(self.btn_color)
        Animation.cancel_all(self.ring_color)
        Animation.cancel_all(self.glow_color)

        if state:
            if sos_mode:
                # SOS Red Alert Theme
                Animation(r=0.94, g=0.27, b=0.27, duration=0.15).start(self.btn_color)
                Animation(r=1, g=0.6, b=0.6, duration=0.15).start(self.ring_color)
                Animation(r=0.94, g=0.27, b=0.27, a=0.45, duration=0.15).start(self.glow_color)
            else:
                # Normal Warm Yellow Theme
                Animation(r=1, g=0.82, b=0.15, duration=0.2).start(self.btn_color)
                Animation(r=1, g=0.92, b=0.5, duration=0.2).start(self.ring_color)
                Animation(r=1, g=0.85, b=0.2, a=0.35, duration=0.2).start(self.glow_color)

            pulse = (
                Animation(glow_radius=40, duration=0.6, t='in_out_quad') +
                Animation(glow_radius=18, duration=0.6, t='in_out_quad')
            )
            pulse.repeat = True
            pulse.bind(on_progress=lambda *x: self.update_canvas())
            pulse.start(self)
        else:
            Animation(r=0.12, g=0.16, b=0.23, duration=0.2).start(self.btn_color)
            Animation(r=0.2, g=0.28, b=0.4, duration=0.2).start(self.ring_color)
            Animation(a=0.0, duration=0.15).start(self.glow_color)
            anim = Animation(glow_radius=0, duration=0.15)
            anim.bind(on_progress=lambda *x: self.update_canvas())
            anim.start(self)


class FlashlightUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=25, spacing=15, **kwargs)
        self.flash_on = False
        self.sos_active = False
        self.blink_event = None
        self.blink_speed = 0

        # SOS Morse Code Pattern (... --- ...)
        # True = Light ON, False = Light OFF, Duration in seconds
        self.sos_pattern = [
            (True, 0.2), (False, 0.2), (True, 0.2), (False, 0.2), (True, 0.2), (False, 0.5),  # S (...)
            (True, 0.6), (False, 0.2), (True, 0.6), (False, 0.2), (True, 0.6), (False, 0.5),  # O (---)
            (True, 0.2), (False, 0.2), (True, 0.2), (False, 0.2), (True, 0.2), (False, 1.2)   # S (...)
        ]
        self.sos_index = 0

        # Auto-off Timer Variables
        self.timer_options = [0, 60, 300, 600]  # Off, 1m, 5m, 10m
        self.timer_labels = ['Timer: OFF', 'Timer: 1m', 'Timer: 5m', 'Timer: 10m']
        self.timer_idx = 0
        self.remaining_seconds = 0
        self.timer_event = None

        # Top Bar (Title + Live Battery)
        top_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.08))
        self.title_lbl = Label(
            text='[b]FLASHLIGHT PRO[/b]',
            markup=True,
            font_size='20sp',
            halign='left',
            color=(0.95, 0.96, 0.98, 1)
        )
        self.title_lbl.bind(size=self.title_lbl.setter('text_size'))
        
        self.battery_lbl = Label(
            text='Battery: --%',
            font_size='15sp',
            halign='right',
            color=(0.3, 0.85, 0.5, 1)
        )
        self.battery_lbl.bind(size=self.battery_lbl.setter('text_size'))
        
        top_bar.add_widget(self.title_lbl)
        top_bar.add_widget(self.battery_lbl)
        self.add_widget(top_bar)

        # Status & Countdown Display
        self.status_lbl = Label(
            text='STATUS: OFF',
            font_size='16sp',
            size_hint=(1, 0.06),
            color=(0.58, 0.64, 0.72, 1)
        )
        self.add_widget(self.status_lbl)

        # Center Animated Glow Button
        self.flash_btn = GlowFlashButton(callback=self.toggle_power, size_hint=(1, 0.44))
        self.add_widget(self.flash_btn)

        # Action Buttons Row (SOS Mode + Auto-Off Timer)
        btn_row = BoxLayout(orientation='horizontal', spacing=15, size_hint=(1, 0.12))
        
        self.sos_btn = Button(
            text='[b]SOS MODE: OFF[/b]',
            markup=True,
            font_size='15sp',
            background_normal='',
            background_color=(0.2, 0.25, 0.35, 1),
            color=(1, 1, 1, 1)
        )
        self.sos_btn.bind(on_release=self.toggle_sos)

        self.timer_btn = Button(
            text='[b]Timer: OFF[/b]',
            markup=True,
            font_size='15sp',
            background_normal='',
            background_color=(0.2, 0.25, 0.35, 1),
            color=(1, 1, 1, 1)
        )
        self.timer_btn.bind(on_release=self.cycle_timer)

        btn_row.add_widget(self.sos_btn)
        btn_row.add_widget(self.timer_btn)
        self.add_widget(btn_row)

        # Bottom Control Card for Blink / Strobe
        self.card = BoxLayout(orientation='vertical', padding=18, spacing=10, size_hint=(1, 0.25))
        with self.card.canvas.before:
            Color(0.12, 0.16, 0.23, 1)
            self.card_bg = RoundedRectangle(radius=[20])
        self.card.bind(pos=self.update_card_bg, size=self.update_card_bg)

        self.blink_lbl = Label(
            text='Blink Mode: OFF (Steady Light)',
            font_size='15sp',
            color=(0.9, 0.94, 1, 1)
        )
        self.card.add_widget(self.blink_lbl)

        self.slider = Slider(
            min=0, max=10, value=0, step=0.5,
            cursor_size=(26, 26)
        )
        self.slider.bind(value=self.on_speed_change)
        self.card.add_widget(self.slider)

        self.add_widget(self.card)

        # Update battery level every 5 seconds
        self.update_battery()
        Clock.schedule_interval(self.update_battery, 5)

    def update_card_bg(self, *args):
        self.card_bg.pos = self.card.pos
        self.card_bg.size = self.card.size

    def update_battery(self, *args):
        if ANDROID_AVAILABLE:
            try:
                level = battery_manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                self.battery_lbl.text = f'Battery: {level}%'
            except Exception:
                self.battery_lbl.text = 'Battery: N/A'
        else:
            self.battery_lbl.text = 'Battery: 100% (Sim)'

    def set_hardware_torch(self, state):
        if ANDROID_AVAILABLE:
            try:
                camera_manager.setTorchMode(camera_id, state)
            except Exception:
                pass

    def toggle_power(self):
        if self.sos_active:
            self.stop_sos()
            return

        self.flash_on = not self.flash_on
        if self.flash_on:
            self.start_timer_if_needed()
            self.update_flash_behavior()
        else:
            self.turn_everything_off()

    def toggle_sos(self, *args):
        if not self.sos_active:
            self.sos_active = True
            self.flash_on = True
            self.sos_btn.text = '[b]SOS MODE: ON[/b]'
            self.sos_btn.background_color = (0.85, 0.2, 0.2, 1)
            self.start_timer_if_needed()
            self.update_flash_behavior()
        else:
            self.stop_sos()

    def stop_sos(self):
        self.sos_active = False
        self.sos_btn.text = '[b]SOS MODE: OFF[/b]'
        self.sos_btn.background_color = (0.2, 0.25, 0.35, 1)
        self.turn_everything_off()

    def cycle_timer(self, *args):
        self.timer_idx = (self.timer_idx + 1) % len(self.timer_options)
        self.remaining_seconds = self.timer_options[self.timer_idx]
        self.timer_btn.text = f'[b]{self.timer_labels[self.timer_idx]}[/b]'

        if self.remaining_seconds > 0:
            self.timer_btn.background_color = (0.15, 0.55, 0.85, 1)
            if self.flash_on:
                self.start_timer_if_needed()
        else:
            self.timer_btn.background_color = (0.2, 0.25, 0.35, 1)
            if self.timer_event:
                self.timer_event.cancel()
                self.timer_event = None
            self.refresh_status_text()

    def start_timer_if_needed(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None

        if self.timer_options[self.timer_idx] > 0:
            self.remaining_seconds = self.timer_options[self.timer_idx]
            self.timer_event = Clock.schedule_interval(self.timer_tick, 1)

    def timer_tick(self, dt):
        self.remaining_seconds -= 1
        self.refresh_status_text()
        if self.remaining_seconds <= 0:
            self.stop_sos() if self.sos_active else self.turn_everything_off()

    def turn_everything_off(self):
        self.flash_on = False
        if self.blink_event:
            self.blink_event.cancel()
            self.blink_event = None
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        self.set_hardware_torch(False)
        self.flash_btn.animate_state(False)
        self.status_lbl.text = 'STATUS: OFF'
        self.status_lbl.color = (0.58, 0.64, 0.72, 1)

    def on_speed_change(self, instance, value):
        self.blink_speed = value
        if value == 0:
            self.blink_lbl.text = 'Blink Mode: OFF (Steady Light)'
        else:
            self.blink_lbl.text = f'Blink Speed: {value:.1f}x / sec'

        if self.flash_on and not self.sos_active:
            self.update_flash_behavior()

    def refresh_status_text(self):
        timer_str = ""
        if self.timer_options[self.timer_idx] > 0 and self.flash_on:
            mins, secs = divmod(self.remaining_seconds, 60)
            timer_str = f" | Auto-Off: {mins:02d}:{secs:02d}"

        if not self.flash_on:
            self.status_lbl.text = 'STATUS: OFF'
            self.status_lbl.color = (0.58, 0.64, 0.72, 1)
        elif self.sos_active:
            self.status_lbl.text = f'STATUS: SOS EMERGENCY{timer_str}'
            self.status_lbl.color = (0.95, 0.3, 0.3, 1)
        elif self.blink_speed == 0:
            self.status_lbl.text = f'STATUS: ON{timer_str}'
            self.status_lbl.color = (1, 0.85, 0.2, 1)
        else:
            self.status_lbl.text = f'STATUS: BLINK ({self.blink_speed:.1f}x){timer_str}'
            self.status_lbl.color = (0.22, 0.74, 0.97, 1)

    def update_flash_behavior(self):
        if self.blink_event:
            self.blink_event.cancel()
            self.blink_event = None

        self.refresh_status_text()

        if self.sos_active:
            self.sos_index = 0
            self.run_sos_step()
        elif self.blink_speed == 0:
            self.set_hardware_torch(True)
            self.flash_btn.animate_state(True, sos_mode=False)
        else:
            self.strobe_state = False
            interval = 1.0 / (self.blink_speed * 2)
            self.blink_event = Clock.schedule_interval(self.blink_tick, interval)

    def run_sos_step(self, *args):
        if not self.sos_active or not self.flash_on:
            return
        state, duration = self.sos_pattern[self.sos_index]
        self.set_hardware_torch(state)
        self.flash_btn.animate_state(state, sos_mode=True)
        self.sos_index = (self.sos_index + 1) % len(self.sos_pattern)
        self.blink_event = Clock.schedule_once(self.run_sos_step, duration)

    def blink_tick(self, dt):
        self.strobe_state = not self.strobe_state
        self.set_hardware_torch(self.strobe_state)
        self.flash_btn.animate_state(self.strobe_state, sos_mode=False)

    def stop_all(self):
        if self.blink_event:
            self.blink_event.cancel()
        if self.timer_event:
            self.timer_event.cancel()
        self.set_hardware_torch(False)


class FlashlightApp(App):
    def build(self):
        self.ui = FlashlightUI()
        return self.ui

    def on_stop(self):
        self.ui.stop_all()


if __name__ == '__main__':
    FlashlightApp().run()
