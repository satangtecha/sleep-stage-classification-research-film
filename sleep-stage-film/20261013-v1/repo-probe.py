"""Small real Manim Slides/3D capability check, no research computation."""
from manim import Cube, Text, VGroup, DEGREES, FadeIn
from manim_slides import ThreeDSlide


class SleepResearchProbe(ThreeDSlide):
    def construct(self):
        self.set_camera_orientation(phi=65 * DEGREES, theta=-65 * DEGREES)
        bars = VGroup(*[
            Cube(side_length=1, fill_opacity=1, fill_color=color).stretch(height, 2).shift([x, 0, height / 2])
            for x, height, color in [(-2, .5642 * 3, "#B2ABFF"), (0, .7486 * 3, "#51D9E8"), (2, .718363 * 3, "#FFCC73")]
        ])
        title = Text("Sleep staging: archived MF1", font_size=30).to_edge([0, 1, 0])
        self.add_fixed_in_frame_mobjects(title)
        self.play(FadeIn(bars), run_time=.5)
        self.next_slide()
        self.begin_ambient_camera_rotation(rate=.15)
        self.wait(2)
        self.next_slide()
