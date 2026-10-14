"""
Manim Studio – English Sleep Stage Evidence
Run:  manim -qh scene.py MainScene
"""

from manim import *
import numpy as np


class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#080F1C"

        # Objects
        bar0 = Rectangle(width=1.667, height=2.696)
        bar0.set_fill(color="#B9ADFF", opacity=1)
        bar0.set_stroke(color="#B9ADFF", width=1)
        bar0.move_to([-3.667, -1.097, 0])

        # Font: Monospace
        label0 = Text("Base 56.42%", font_size=27, color="#F1F5FC", font="Monospace")
        label0.move_to([-3.667, -2.889, 0])

        bar1 = Rectangle(width=1.667, height=3.577)
        bar1.set_fill(color="#58DFEE", opacity=1)
        bar1.set_stroke(color="#58DFEE", width=1)
        bar1.move_to([0.000, -0.656, 0])

        # Font: Monospace
        label1 = Text("R1 74.86%", font_size=27, color="#F1F5FC", font="Monospace")
        label1.move_to([0.000, -2.889, 0])

        bar2 = Rectangle(width=1.667, height=3.432)
        bar2.set_fill(color="#FFD08A", opacity=1)
        bar2.set_stroke(color="#FFD08A", width=1)
        bar2.move_to([3.667, -0.728, 0])

        # Font: Monospace
        label2 = Text("Full-night 71.84%", font_size=27, color="#F1F5FC", font="Monospace")
        label2.move_to([3.667, -2.889, 0])

        # Font: Monospace
        title = Text("Archived subject-mean macro-F1", font_size=30, color="#ABB9CC", font="Monospace")
        title.move_to([0.000, 3.167, 0])

        # Font: Monospace
        caveat = Text("R1: post-hoc and transductive. Not paper replication.", font_size=19, color="#ABB9CC", font="Monospace")
        caveat.move_to([0.000, 2.444, 0])

        # Animation
        self.play(FadeIn(bar0), run_time=0.5)
        self.play(FadeIn(label0), run_time=0.5)
        self.play(FadeIn(bar1), run_time=0.5)
        self.play(FadeIn(label1), run_time=0.5)
        self.play(FadeIn(bar2), run_time=0.5)
        self.play(FadeIn(label2), run_time=0.5)
        self.play(FadeIn(title), run_time=0.5)
        self.play(FadeIn(caveat), run_time=0.5)

        self.wait(1)
