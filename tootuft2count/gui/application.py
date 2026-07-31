"""Application entry point."""


def launch_gui():
    import napari
    from .workflow_widget import WorkflowWidget

    viewer = napari.Viewer(title="tootuft2count workflow")
    viewer.window.add_dock_widget(WorkflowWidget(viewer), name="tootuft2count", area="right")
    napari.run()
