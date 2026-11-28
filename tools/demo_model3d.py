"""Render the STEP file of the recorded session as a turning 3D model, for the demo video.

Run from the repo root, after `python -m tools.demo_record`:  python -m tools.demo_model3d

It reads `demo/run/revA.step` (the file the server made), not the shaft data. So the pictures show
what a CAD program gets. Output: `demo/run/model/m000.png` ... (1920x1080, one per video frame).
"""

from pathlib import Path

import cadquery as cq
import vtk

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "demo" / "run"
OUT = RUN / "model"
FRAMES = 150  # 5 seconds at 30 frames per second
W, H = 1920, 1080


def main() -> None:
    OUT.mkdir(exist_ok=True)
    shape = cq.importers.importStep(str(RUN / "revA.step")).val()
    vertices, triangles = shape.tessellate(0.02, 0.1)

    points = vtk.vtkPoints()
    for v in vertices:
        points.InsertNextPoint(v.x, v.y, v.z)
    cells = vtk.vtkCellArray()
    for a, b, c in triangles:
        cells.InsertNextCell(3)
        for i in (a, b, c):
            cells.InsertCellPoint(i)
    mesh = vtk.vtkPolyData()
    mesh.SetPoints(points)
    mesh.SetPolys(cells)

    clean = vtk.vtkCleanPolyData()
    clean.SetInputData(mesh)
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(clean.GetOutputPort())
    normals.SetFeatureAngle(35)
    normals.SplittingOn()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    body = vtk.vtkActor()
    body.SetMapper(mapper)
    p = body.GetProperty()
    p.SetColor(0.72, 0.76, 0.80)  # steel
    p.SetSpecular(0.55)
    p.SetSpecularPower(40)
    p.SetDiffuse(0.75)
    p.SetAmbient(0.18)

    # The sharp edges, as a CAD program draws them.
    edges = vtk.vtkFeatureEdges()
    edges.SetInputConnection(clean.GetOutputPort())
    edges.BoundaryEdgesOff()
    edges.ManifoldEdgesOff()
    edges.NonManifoldEdgesOff()
    edges.FeatureEdgesOn()
    edges.SetFeatureAngle(35)
    edge_mapper = vtk.vtkPolyDataMapper()
    edge_mapper.SetInputConnection(edges.GetOutputPort())
    edge_mapper.ScalarVisibilityOff()
    lines = vtk.vtkActor()
    lines.SetMapper(edge_mapper)
    lines.GetProperty().SetColor(0.05, 0.07, 0.06)
    lines.GetProperty().SetLineWidth(2.0)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(9 / 255, 12 / 255, 11 / 255)
    renderer.AddActor(body)
    renderer.AddActor(lines)
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetMultiSamples(8)
    window.SetSize(W, H)
    window.AddRenderer(renderer)

    normals.Update()
    x0, x1, y0, y1, z0, z1 = normals.GetOutput().GetBounds()
    centre = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    long_axis = max(range(3), key=lambda i: (x1 - x0, y1 - y0, z1 - z0)[i])
    camera = renderer.GetActiveCamera()
    camera.SetFocalPoint(*centre)
    start = [centre[0], centre[1], centre[2]]
    side = (long_axis + 1) % 3
    up = (long_axis + 2) % 3
    start[side] += 300
    start[up] += 110
    start[long_axis] += 120
    camera.SetPosition(*start)
    view_up = [0.0, 0.0, 0.0]
    view_up[up] = 1.0
    camera.SetViewUp(*view_up)
    renderer.ResetCamera()
    camera.Zoom(1.45)
    renderer.ResetCameraClippingRange()

    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(window)
    writer = vtk.vtkPNGWriter()
    writer.SetInputConnection(grab.GetOutputPort())
    camera.Azimuth(-55)  # so the keyway faces the camera in the middle of the turn
    for i in range(FRAMES):
        window.Render()
        grab.Modified()
        writer.SetFileName(str(OUT / f"m{i:03d}.png"))
        writer.Write()
        camera.Azimuth(360 / FRAMES * 0.6)  # a slow turn: 216 degrees in all
        renderer.ResetCameraClippingRange()
    print(f"{FRAMES} pictures in {OUT}; long axis {'xyz'[long_axis]}; size {x1 - x0:.0f} x {y1 - y0:.0f} x {z1 - z0:.0f}")


if __name__ == "__main__":
    main()
