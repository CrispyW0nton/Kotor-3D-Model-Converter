"""Media player widget: play/pause, seek, volume, and waveform for WAV/audio in the toolset."""

from __future__ import annotations

from typing import TYPE_CHECKING

import qtpy

from qtpy.QtCore import QBuffer, QPoint, Qt, Signal
from qtpy.QtGui import QKeySequence
from qtpy.QtMultimedia import QMediaPlayer
from qtpy.QtWidgets import (
    QStyle,
    QWidget,
)

if TYPE_CHECKING:
    from qtpy.QtCore import QTimer
    from qtpy.QtGui import QKeyEvent, QMouseEvent, QShowEvent, QWheelEvent
    from qtpy.QtMultimedia import QAudioOutput


class MediaPlayerWidget(QWidget):
    """Industry-standard media player widget with comprehensive controls.

    Features:
    - Play/pause, stop, and mute controls
    - Volume control with slider
    - Playback speed control
    - Time slider with seeking
    - Keyboard shortcuts (Space, Left/Right arrows, Up/Down arrows)
    - Progress preview on hover
    - Better error handling
    - Qt5 and Qt6 compatibility
    - Status indicators
    """

    # Signals for external integration
    playback_started = Signal()
    playback_paused = Signal()
    playback_stopped = Signal()
    position_changed = Signal(int)  # position in milliseconds
    volume_changed = Signal(float)  # volume 0.0-1.0
    playback_speed_changed = Signal(float)  # playback rate

    def __init__(
        self,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.buffer: QBuffer = QBuffer(self)
        self.player: QMediaPlayer = QMediaPlayer(self)

        # State tracking
        self._is_seeking: bool = False
        self._previous_volume: float = 0.75  # Default volume
        self._is_muted: bool = False
        self._drag_position: QPoint = QPoint()
        self._hover_position: QPoint = QPoint()
        self._hover_timer: QTimer | None = None

        # Audio output for Qt6
        self._audio_output: QAudioOutput | None = None

        # Playback speed levels (industry-standard range)
        self.speed_levels: list[float] = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        self.current_speed_index: int = 3  # Default to 1.0x

        self._setup_audio_output()
        self._setup_media_player()
        self._setup_signals()
        self._setup_keyboard_shortcuts()
        self.hide_widget()

    def _setup_audio_output(self) -> None:
        """Set up audio output for Qt6 compatibility."""
        if not qtpy.QT6:
            return

        # Only set up if not already configured (allows external setup)
        if self._audio_output is None:
            from qtpy.QtMultimedia import QAudioOutput  # pyright: ignore[reportAttributeAccessIssue]

            self._audio_output = QAudioOutput(self)  # type: ignore[call-overload]
            self._audio_output.setVolume(self._previous_volume)
            self.player.setAudioOutput(self._audio_output)  # type: ignore[arg-type]
        else:
            # Update volume if audio output already exists
            self._audio_output.setVolume(self._previous_volume)  # type: ignore[attr-defined]

    def _setup_media_player(self) -> None:
        """Set up the media player UI components."""
        # Load UI from .ui file
        from toolset.uic.qtpy.widgets.media_player_widget import Ui_MediaPlayerWidget

        self.ui = Ui_MediaPlayerWidget()
        self.ui.setupUi(self)

        # Get references to UI widgets
        self.play_pause_button = self.ui.playPauseButton
        self.stop_button = self.ui.stopButton
        self.time_slider = self.ui.timeSlider
        self.time_label = self.ui.timeLabel
        self.mute_button = self.ui.muteButton
        self.volume_slider = self.ui.volumeSlider
        self.speed_button = self.ui.speedButton

        # Set up icons for buttons
        q_style: QStyle | None = self.style()
        assert q_style is not None, "q_style is somehow None"
        self.play_pause_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.stop_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.mute_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume))

        # Set up time slider behavior
        self._setup_time_slider()

        # Set up volume controls
        self._setup_volume_controls()

        # Set up speed controls
        self._setup_speed_controls()

        # Set stretch factor for time slider (make it expandable)
        self.ui.controlsLayout.setStretch(2, 1)  # timeSlider is at index 2

    def _setup_time_slider(self) -> None:
        """Set up the time/position slider with enhanced seeking."""
        # Time slider is already created from .ui file, just configure behavior
        # Custom slider behavior for better seeking
        self._setup_custom_slider_behavior()

    def _setup_custom_slider_behavior(self) -> None:
        """Set up custom mouse and keyboard behavior for the time slider."""
        original_mouse_press = self.time_slider.mousePressEvent
        original_mouse_move = self.time_slider.mouseMoveEvent
        original_mouse_release = self.time_slider.mouseReleaseEvent
        original_wheel = self.time_slider.wheelEvent

        def mouse_press_event(ev: QMouseEvent) -> None:
            if ev.button() == Qt.MouseButton.LeftButton:
                # Calculate position based on click location
                value = self._slider_value_from_position(ev.pos().x())
                self._is_seeking = True
                self.player.pause()
                self.time_slider.setValue(value)
                self.player.setPosition(value)
                self._drag_position = ev.pos()
                ev.accept()
            else:
                original_mouse_press(ev)

        def mouse_move_event(ev: QMouseEvent) -> None:
            if self._is_seeking and ev.buttons() == Qt.MouseButton.LeftButton:
                value = self._slider_value_from_position(ev.pos().x())
                self.time_slider.setValue(value)
                self.player.setPosition(value)
                self._drag_position = ev.pos()
                ev.accept()
            else:
                # Track hover position for preview
                self._hover_position = ev.pos()
                original_mouse_move(ev)

        def mouse_release_event(ev: QMouseEvent) -> None:
            if ev.button() == Qt.MouseButton.LeftButton and self._is_seeking:
                value = self._slider_value_from_position(ev.pos().x())
                self.time_slider.setValue(value)
                self.player.setPosition(value)
                self.player.play()
                self._is_seeking = False
                self._drag_position = QPoint()
                ev.accept()
            else:
                original_mouse_release(ev)

        def wheel_event(ev: QWheelEvent) -> None:
            """Seek with mouse wheel."""
            if self.time_slider.maximum() == 0:
                return

            delta = ev.angleDelta().y()
            step = 5000 if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1000
            current = self.time_slider.value()
            new_value = max(0, min(self.time_slider.maximum(), current + (step if delta > 0 else -step)))
            self.time_slider.setValue(new_value)
            self.player.setPosition(new_value)
            ev.accept()

        self.time_slider.mousePressEvent = mouse_press_event  # type: ignore[assignment]
        self.time_slider.mouseMoveEvent = mouse_move_event  # type: ignore[assignment]
        self.time_slider.mouseReleaseEvent = mouse_release_event  # type: ignore[assignment]
        self.time_slider.wheelEvent = wheel_event  # type: ignore[assignment]

    def _slider_value_from_position(self, x: int) -> int:
        """Calculate slider value from mouse X position."""
        if self.time_slider.width() == 0 or self.time_slider.maximum() == 0:
            return 0
        ratio = max(0.0, min(1.0, (x - self.time_slider.rect().x()) / self.time_slider.width()))
        return int(ratio * self.time_slider.maximum())

    def _setup_volume_controls(self) -> None:
        """Set up volume control with slider and mute button."""
        # Volume controls are already created from .ui file, just configure
        self.volume_slider.setValue(int(self._previous_volume * 100))
        self.volume_slider.setToolTip(f"Volume: {int(self._previous_volume * 100)}% (Up/Down arrows)")
        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)

    def _setup_speed_controls(self) -> None:
        """Set up playback speed control."""
        # Speed button is already created from .ui file, just connect signal
        self.speed_button.clicked.connect(self._cycle_playback_speed)

    def _setup_signals(self) -> None:
        """Connect all signal handlers."""
        # Player signals
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)

        state_changed = self.player.stateChanged if qtpy.QT5 else self.player.playbackStateChanged  # type: ignore[attr-defined]
        state_changed.connect(self._on_state_changed)

        # Error handling
        if qtpy.QT5:
            self.player.error.connect(self._on_error)  # type: ignore[attr-defined]
        else:
            self.player.errorOccurred.connect(self._on_error)  # type: ignore[attr-defined]

        # Button signals
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.stop)
        self.mute_button.clicked.connect(self.toggle_mute)

    def _setup_keyboard_shortcuts(self) -> None:
        """Set up keyboard shortcuts for media control."""
        from qtpy.QtWidgets import QShortcut

        # Space: Play/Pause
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play_pause)

        # S: Stop
        QShortcut(QKeySequence(Qt.Key.Key_S), self, self.stop)

        # Left/Right: Seek backward/forward (5 seconds)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.seek_relative(-5000))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.seek_relative(5000))

        # Shift+Left/Right: Seek backward/forward (1 second)
        QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Left), self, lambda: self.seek_relative(-1000))
        QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Right), self, lambda: self.seek_relative(1000))

        # Up/Down: Volume up/down
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, self.volume_up)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, self.volume_down)

        # M: Mute
        QShortcut(QKeySequence(Qt.Key.Key_M), self, self.toggle_mute)

        # [ ]: Playback speed
        QShortcut(QKeySequence(Qt.Key.Key_BracketLeft), self, lambda: self.change_playback_speed(-1))
        QShortcut(QKeySequence(Qt.Key.Key_BracketRight), self, lambda: self.change_playback_speed(1))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard events for media control."""
        if event.key() == Qt.Key.Key_Space:
            self.toggle_play_pause()
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            self.seek_relative(-5000 if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier else -1000)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            self.seek_relative(5000 if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1000)
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            self.volume_up()
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            self.volume_down()
            event.accept()
        else:
            super().keyPressEvent(event)

    # Public control methods

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        state_enum = QMediaPlayer.State if qtpy.QT5 else QMediaPlayer.PlaybackState  # type: ignore[attr-defined]
        state_getter = self.player.state if qtpy.QT5 else self.player.playbackState  # type: ignore[attr-defined]
        q_style: QStyle | None = self.style()
        assert q_style is not None, "q_style is somehow None"

        current_state = state_getter()
        if current_state == state_enum.PlayingState:
            self.player.pause()
            self.play_pause_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.playback_paused.emit()
        else:
            self.player.play()
            self.play_pause_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.show_widget()
            self.playback_started.emit()

    def play(self) -> None:
        """Start playback."""
        self.player.play()
        q_style: QStyle | None = self.style()
        assert q_style is not None, "q_style is somehow None"
        self.play_pause_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.show_widget()
        self.playback_started.emit()

    def pause(self) -> None:
        """Pause playback."""
        self.player.pause()
        q_style: QStyle | None = self.style()
        assert q_style is not None, "q_style is somehow None"
        self.play_pause_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.playback_paused.emit()

    def stop(self) -> None:
        """Stop playback and reset position."""
        self.player.stop()
        q_style: QStyle | None = self.style()
        assert q_style is not None, "q_style is somehow None"
        self.play_pause_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.hide_widget()
        self.playback_stopped.emit()

    def seek_relative(self, delta_ms: int) -> None:
        """Seek relative to current position."""
        current = self.player.position()
        duration = self.player.duration()
        new_position = max(0, min(duration if duration > 0 else current, current + delta_ms))
        self.player.setPosition(new_position)
        self.time_slider.setValue(new_position)

    def seek_absolute(self, position_ms: int) -> None:
        """Seek to absolute position."""
        duration = self.player.duration()
        position = max(0, min(duration if duration > 0 else position_ms, position_ms))
        self.player.setPosition(position)
        self.time_slider.setValue(position)

    def toggle_mute(self) -> None:
        """Toggle mute state."""
        if qtpy.QT5:
            self._is_muted = not self.player.isMuted()  # type: ignore[attr-defined]
            self.player.setMuted(self._is_muted)  # type: ignore[attr-defined]
        else:
            # Get audio output from player (may have been set externally)
            audio_output = self.player.audioOutput()  # type: ignore[attr-defined]
            if audio_output is None:
                self._setup_audio_output()
                audio_output = self._audio_output

            if audio_output is not None:
                current_volume = audio_output.volume()  # type: ignore[attr-defined]
                if current_volume > 0:
                    self._previous_volume = current_volume
                    audio_output.setVolume(0)  # type: ignore[attr-defined]
                    self._is_muted = True
                else:
                    audio_output.setVolume(self._previous_volume)  # type: ignore[attr-defined]
                    self._is_muted = False

        self._update_mute_icon()

    def _update_mute_icon(self) -> None:
        """Update mute button icon based on current state."""
        q_style: QStyle | None = self.style()
        assert q_style is not None, "q_style is somehow None"

        if self._is_muted:
            self.mute_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
            self.mute_button.setToolTip("Unmute (M)")
        else:
            self.mute_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
            volume_percent = int(self.volume() * 100)
            self.mute_button.setToolTip(f"Mute (M) - Volume: {volume_percent}%")

    def volume(self) -> float:
        """Get current volume (0.0-1.0)."""
        if qtpy.QT5:
            return self.player.volume() / 100.0  # type: ignore[attr-defined]
        else:
            # Get audio output from player (may have been set externally)
            audio_output = self.player.audioOutput()  # type: ignore[attr-defined]
            if audio_output is None:
                return self._previous_volume
            current_vol = audio_output.volume()  # type: ignore[attr-defined]
            self._previous_volume = current_vol
            return current_vol

    def set_volume(self, volume: float) -> None:
        """Set volume (0.0-1.0)."""
        volume = max(0.0, min(1.0, volume))
        self._previous_volume = volume

        if qtpy.QT5:
            self.player.setVolume(int(volume * 100))  # type: ignore[attr-defined]
        else:
            # Get audio output from player (may have been set externally)
            audio_output = self.player.audioOutput()  # type: ignore[attr-defined]
            if audio_output is None:
                self._setup_audio_output()
                audio_output = self._audio_output

            if audio_output is not None:
                audio_output.setVolume(volume)  # type: ignore[attr-defined]

        if volume > 0:
            self._is_muted = False

        self.volume_slider.setValue(int(volume * 100))
        self._update_mute_icon()
        self.volume_changed.emit(volume)

    def sync_volume_from_player(self) -> None:
        """Sync volume slider with current player volume (useful when audio output is set externally)."""
        current_vol = self.volume()
        self._previous_volume = current_vol
        self.volume_slider.setValue(int(current_vol * 100))
        self._update_mute_icon()

    def volume_up(self) -> None:
        """Increase volume by 5%."""
        new_volume = min(1.0, self.volume() + 0.05)
        self.set_volume(new_volume)

    def volume_down(self) -> None:
        """Decrease volume by 5%."""
        new_volume = max(0.0, self.volume() - 0.05)
        self.set_volume(new_volume)

    def _on_volume_slider_changed(self, value: int) -> None:
        """Handle volume slider change."""
        volume = value / 100.0
        self.set_volume(volume)
        self.volume_slider.setToolTip(f"Volume: {value}% (Up/Down arrows)")

    def change_playback_speed(self, direction: int) -> None:
        """Change playback speed by direction (-1 for slower, +1 for faster)."""
        self.current_speed_index = max(0, min(len(self.speed_levels) - 1, self.current_speed_index + direction))
        new_rate = self.speed_levels[self.current_speed_index]
        self.set_playback_speed(new_rate)

    def set_playback_speed(self, rate: float) -> None:
        """Set playback speed (0.25-2.0)."""
        # Find closest speed level
        closest_index = min(range(len(self.speed_levels)), key=lambda i: abs(self.speed_levels[i] - rate))
        self.current_speed_index = closest_index
        rate = self.speed_levels[self.current_speed_index]

        state_enum = QMediaPlayer.State if qtpy.QT5 else QMediaPlayer.PlaybackState  # type: ignore[attr-defined]
        state_getter = self.player.state if qtpy.QT5 else self.player.playbackState  # type: ignore[attr-defined]
        was_playing = state_getter() == state_enum.PlayingState
        current_position = self.player.position()

        self.player.setPlaybackRate(rate)
        self.player.setPosition(current_position)

        if was_playing:
            self.player.play()

        self.speed_button.setText(f"{rate:.2f}x")
        self.playback_speed_changed.emit(rate)

    def _cycle_playback_speed(self) -> None:
        """Cycle through playback speeds."""
        self.current_speed_index = (self.current_speed_index + 1) % len(self.speed_levels)
        rate = self.speed_levels[self.current_speed_index]
        self.set_playback_speed(rate)

    # Signal handlers

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState | QMediaPlayer.State) -> None:
        """Handle playback state changes."""
        state_enum = QMediaPlayer.State if qtpy.QT5 else QMediaPlayer.PlaybackState  # type: ignore[attr-defined]
        q_style: QStyle | None = self.style()
        assert q_style is not None, "q_style is somehow None"

        if state == state_enum.PlayingState:
            self.show_widget()
            self.play_pause_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_pause_button.setIcon(q_style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """Handle media status changes."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.time_slider.setValue(self.time_slider.maximum())
            self.stop()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._on_error()

    def _on_position_changed(self, position: int) -> None:
        """Handle position updates."""
        if not self._is_seeking and not self.time_slider.isSliderDown():
            self.time_slider.setValue(position)

        current_time = self.format_time(position)
        total_time = self.format_time(self.time_slider.maximum())
        self.time_label.setText(f"{current_time} / {total_time}")
        self.position_changed.emit(position)

    def _on_duration_changed(self, duration: int) -> None:
        """Handle duration updates."""
        self.time_slider.setRange(0, duration if duration > 0 else 0)
        total_time = self.format_time(duration)
        current_time = self.format_time(self.time_slider.value())
        self.time_label.setText(f"{current_time} / {total_time}")

    def _on_error(self, *args, **kwargs) -> None:
        """Handle player errors."""
        error = self.player.error() if qtpy.QT5 else self.player.error()  # type: ignore[attr-defined]
        error_string = self.player.errorString() if qtpy.QT5 else self.player.errorString()  # type: ignore[attr-defined]

        # Log error but don't crash - just stop playback
        from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]

        RobustLogger().warning(f"Media player error: {error_string} (error code: {error})")
        self.stop()

    # Utility methods

    def format_time(self, msecs: int) -> str:
        """Format milliseconds as MM:SS or HH:MM:SS."""
        if msecs < 0:
            msecs = 0
        total_seconds = msecs // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def show_widget(self) -> None:
        """Show the media player widget."""
        self.show()
        self.play_pause_button.show()
        self.stop_button.show()
        self.mute_button.show()
        self.volume_slider.show()
        self.time_label.show()
        self.time_slider.show()
        self.speed_button.show()

    def hide_widget(self) -> None:
        """Hide the media player widget."""
        self.hide()
        self.play_pause_button.hide()
        self.stop_button.hide()
        self.mute_button.hide()
        self.volume_slider.hide()
        self.time_label.hide()
        self.time_slider.hide()
        self.speed_button.hide()

    def setVisible(self, visible: bool) -> None:  # noqa: FBT001
        """Override to control visibility based on player state."""
        if not visible:
            super().setVisible(False)
            return

        state_enum = QMediaPlayer.State if qtpy.QT5 else QMediaPlayer.PlaybackState  # type: ignore[attr-defined]
        state_getter = self.player.state if qtpy.QT5 else self.player.playbackState  # type: ignore[attr-defined]
        if state_getter() == state_enum.PlayingState:
            super().setVisible(True)

    def showEvent(self, event: QShowEvent) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]  # noqa: N802
        """Override to handle show events."""
        super().showEvent(event)
