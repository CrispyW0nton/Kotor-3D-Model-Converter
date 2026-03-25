using System.Timers;
using System;
using Avalonia.Controls;
using Avalonia.OpenGL;
using Avalonia.OpenGL.Controls;
using Kotor.NET.Graphics;
using Avalonia.Threading;
using Silk.NET.OpenGLES;
using Avalonia;
using Kotor.NET.Graphics.SceneObjects;
using MapBuilder.Render;
using Avalonia.Input;
using Avalonia.Platform;
using Avalonia.Media;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Reflection;
using System.IO;

namespace MapBuilder.Views;

public partial class MainView : UserControl
{
    public MainView()
    {
        InitializeComponent();
    }
}


public class KotorGLControl : OpenGlControlBase
{
    private GL _gl;
    private Scene _scene;

    private uint _width = 0;
    private uint _height = 0;
    private bool _init = false;

    private HashSet<bool> _mouseButtons = new();
    private Point _mousePosition = new();

    public KotorGLControl()
    {
        Timer timer = new(33);
        timer.Elapsed += OnTimedEvent;
        timer.Start();
    }

    protected override unsafe void OnOpenGlInit(GlInterface glInterface)
    {
        GL gl = _gl = GL.GetApi(glInterface.GetProcAddress);
        Graphics graphics = new(gl);

        _scene = new(gl, graphics);
        _scene.Init();

        var assembly = Assembly.GetExecutingAssembly();
        graphics.Shaders.Add("terrain", new(_gl, assembly.GetManifestResourceStream($"MapBuilder.Resources.terrain.vshader")!, assembly.GetManifestResourceStream($"MapBuilder.Resources.terrain.fshader")!));

        _scene.AddObject(new MapObject(graphics));

        _init = true;
        _gl.Viewport(0, 0, _width, _height);
    }

    protected override unsafe void OnOpenGlDeinit(GlInterface gl)
    {

    }

    protected override unsafe void OnOpenGlRender(GlInterface gl, int fb)
    {
        if (_init)
        {
            _scene.Render((uint)_width, (uint)_height, (uint)(_width * 1.0f), (uint)(_height * 1.0f));

            var mouseInWorld = _scene.FromScreenSpaceToWorldSpace((uint)_mousePosition.X, (uint)_mousePosition.Y);
            _scene.Camera.MouseX = mouseInWorld.X;
            _scene.Camera.MouseY = mouseInWorld.Y;
            _scene.Camera.MouseZ = mouseInWorld.Z;
        }
    }

    private void OnTimedEvent(Object source, ElapsedEventArgs e)
    {
        Dispatcher.UIThread.Invoke(() =>
        {
            RequestNextFrameRendering();
        });
    }

    protected override void OnSizeChanged(SizeChangedEventArgs e)
    {
        var scaling = GetParentWindow().RenderScaling;
        _width = (uint)(e.NewSize.Width * scaling);
        _height = (uint)(e.NewSize.Height * scaling);
    }

    protected override void OnPointerPressed(PointerPressedEventArgs e)
    {
        base.OnPointerPressed(e);
    }

    protected override void OnPointerMoved(PointerEventArgs e)
    {
        base.OnPointerMoved(e);
        _mousePosition = e.GetPosition(this);

        var camera = _scene.Camera;

        var oldPoint = e.GetIntermediatePoints(this).First();
        var newPoint = e.GetCurrentPoint(this);
        var delta = newPoint.Position - oldPoint.Position;

        if (newPoint.Properties.IsMiddleButtonPressed)
        {
            camera.Yaw += (float)(Math.PI * -delta.X * 0.001);
            camera.Pitch += (float)(Math.PI * delta.Y * 0.001);
        }

        if (newPoint.Properties.IsLeftButtonPressed && e.KeyModifiers == KeyModifiers.Control)
        {
            camera.TargetX += (float)(delta.X * 0.01 * MathF.Sin(camera.Yaw)) - (float)(delta.Y * 0.01 * MathF.Cos(camera.Yaw));
            camera.TargetY -= (float)(delta.X * 0.01 * MathF.Cos(camera.Yaw)) + (float)(delta.Y * 0.01 * MathF.Sin(camera.Yaw));
        }
    }

    protected override void OnPointerWheelChanged(PointerWheelEventArgs e)
    {
        base.OnPointerWheelChanged(e);

        _scene.Camera.Distance -= (float)(e.Delta.Y * 0.4);
    }

    public override void Render(DrawingContext context)
    {
        context.FillRectangle(Brushes.Red, new Rect(Bounds.Size));

        base.Render(context);
    }

    private Window GetParentWindow()
    {
        dynamic node = this;

        while (true)
        {
            if (node.Parent is null)
                return (Window)node;

            node = node.Parent;
        }
    }
}
