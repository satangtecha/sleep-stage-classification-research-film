"""
Manim Studio – Sleep Stage Results - measured aggregate values
Run:  manim -qh scene.py MainScene
"""

from manim import *
import numpy as np


class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#081321"

        # Objects
        bar0 = Rectangle(width=1.778, height=2.445)
        bar0.set_fill(color="#B2ABFF", opacity=1)
        bar0.set_stroke(color="#B2ABFF", width=2)
        bar0.move_to([-3.556, -1.222, 0])

        # Font: Arial
        label0 = Text("Text", font_size=30, color="#EFF6FF", font="Arial")
        label0.move_to([-3.556, -2.889, 0])

        bar1 = Rectangle(width=1.778, height=3.244)
        bar1.set_fill(color="#51D9E8", opacity=1)
        bar1.set_stroke(color="#51D9E8", width=2)
        bar1.move_to([0.000, -0.823, 0])

        # Font: Arial
        label1 = Text("Text", font_size=30, color="#EFF6FF", font="Arial")
        label1.move_to([0.000, -2.889, 0])

        bar2 = Rectangle(width=1.778, height=3.113)
        bar2.set_fill(color="#FFCC73", opacity=1)
        bar2.set_stroke(color="#FFCC73", width=2)
        bar2.move_to([3.556, -0.888, 0])

        # Font: Arial
        label2 = Text("Text", font_size=30, color="#EFF6FF", font="Arial")
        label2.move_to([3.556, -2.889, 0])

        # Font: Arial
        title = Text("Text", font_size=32, color="#EFF6FF", font="Arial")
        title.move_to([0.000, 3.167, 0])

        # Animation
        self.play(FadeIn(bar0), run_time=0.5)
        self.play(FadeIn(label0), run_time=0.5)
        self.play(FadeIn(bar1), run_time=0.5)
        self.play(FadeIn(label1), run_time=0.5)
        self.play(FadeIn(bar2), run_time=0.5)
        self.play(FadeIn(label2), run_time=0.5)
        self.play(FadeIn(title), run_time=0.5)

        self.wait(1)
