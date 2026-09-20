from manim import *

class BiggerNetwork(Scene):

    def construct(self):

        # Node positions
        p0 = LEFT * 2
        p1 = UP * 1.5
        p2 = RIGHT * 1.5
        p3 = DOWN * 1.5
        p4 = RIGHT * 2.5 + DOWN * 1.5

        # Nodes
        n0 = Circle(radius=0.3, color=BLUE, fill_opacity=0.2)
        n1 = Circle(radius=0.3, color=BLUE, fill_opacity=0.2)
        n2 = Circle(radius=0.3, color=BLUE, fill_opacity=0.2)
        n3 = Circle(radius=0.3, color=BLUE, fill_opacity=0.2)
        n4 = Circle(radius=0.3, color=BLUE, fill_opacity=0.2)
        nodes = VGroup(n0, n1, n2, n3, n4)

        for p,n in zip([p0, p1, p2, p3, p4], [n0, n1, n2, n3, n4]):
            n.move_to(p)

        # Edges
        arrow_kwargs = {
            'tip_length': 0.15,                      # Sets fixed absolute arrowhead length (in Manim units)
            'max_tip_length_to_length_ratio': 1.0,  # Prevents Manim from shrinking tips on shorter arrows
            'buff': 0.33,
        }

        
        e01 = Arrow(p0, p1, **arrow_kwargs)
        e02 = Arrow(p0, p2, **arrow_kwargs)
        e03 = Arrow(p0, p3, **arrow_kwargs)
        e12 = Arrow(p1, p2, **arrow_kwargs)
        e24 = Arrow(p2, p4, **arrow_kwargs)
        e34 = Arrow(p3, p4, **arrow_kwargs)
        edges = VGroup(e01, e02, e03, e12, e24, e34)

        # Draw nodes
        self.play(Create(n0), Create(n1), Create(n2), Create(n3), Create(n4),)
        # Draw edges
        self.play(GrowArrow(e01), GrowArrow(e02), GrowArrow(e03), GrowArrow(e12), GrowArrow(e24), GrowArrow(e34),)

        self.play(nodes.animate.shift(LEFT), edges.animate.shift(LEFT), run_time=2)



        # Make labels
        l0 = MathTex("0").next_to(n0, DOWN)
        l1 = MathTex("1").next_to(n1, UP)
        l2 = MathTex("2").next_to(n2, UP)
        l3 = MathTex("3").next_to(n3, DOWN)
        l4 = MathTex("4").next_to(n4, DOWN)        
        self.play(Write(l0), Write(l1), Write(l2), Write(l3), Write(l4),)

        self.play(e02.animate.set_color(YELLOW).set_stroke(width=7))
        self.play(n2.animate.set_color(RED).set_fill(RED, opacity=0.5).scale(1.25), run_time=2)

        interdiction = MathTex(r"y_2 = 1")
        interdiction.to_edge(RIGHT)
        self.play(Write(interdiction))

        self.play(e02.animate.set_opacity(0.2), e12.animate.set_opacity(0.2), e24.animate.set_opacity(0.2),)


        self.wait(2)