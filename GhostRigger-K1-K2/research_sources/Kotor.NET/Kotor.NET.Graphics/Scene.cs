using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorMDL;
using Kotor.NET.Formats.KotorTPC;
using Kotor.NET.Graphics.Extensions;
using Kotor.NET.Graphics.SceneObjects;
using Silk.NET.OpenGLES;

namespace Kotor.NET.Graphics
{
    public class Scene
    {
        public Camera Camera = new();

        private List<SceneObject> _objects = new();
        private Graphics _graphics;
        private Frame _frame = new();
        private GL _gl;

        public Scene(GL gl, Graphics graphics)
        {
            _gl = gl;
            _graphics = graphics;
        }

        public void Init()
        {
            _gl.DebugMessageCallback(DebugMessageDelegate, IntPtr.Zero);
            _gl.Enable(EnableCap.DebugOutput);
            _gl.Enable(EnableCap.DepthTest);

            var assembly = Assembly.GetExecutingAssembly();
            _graphics.Shaders.Add("kotor", new(_gl, assembly.GetManifestResourceStream($"Kotor.NET.Graphics.Resources.kotor.vshader")!, assembly.GetManifestResourceStream($"Kotor.NET.Graphics.Resources.kotor.fshader")!));

            _graphics.Textures.Add("lda_grass01", new Texture(_gl, new TGABinaryReader(File.ReadAllBytes(@"Assets/lda_grass01.tga")).Read()));
            _graphics.Textures.Add("plc_jnkspdr1", new Texture(_gl, new TGABinaryReader(File.ReadAllBytes(@"Assets/plc_jnkspdr1.tga")).Read() ));
            _graphics.Textures.Add("plc_spdrwin01", new Texture(_gl, new TGABinaryReader(File.ReadAllBytes(@"Assets/plc_spdrwin01.tga")).Read() ));

            //var thingy = new KotorModelLoader(File.ReadAllBytes(@"Assets\plc_jnkspdr1.mdl"), File.ReadAllBytes(@"Assets\plc_jnkspdr1.mdx")).Read(_graphics);
            //_objects.Add(thingy);

            CubeObject.InitializeVertexArray(_gl, _graphics);
            TriangleObject.InitializeVertexArray(_gl, _graphics);
        }

        public void Render(uint windowWidth, uint windowHeight, uint width, uint height)
        {
            if (width != Camera.Width || height != Camera.Height)
            {
                Camera.Width = width;
                Camera.Height = height;
                _gl.Viewport(0, 0, width, height);
            }

            foreach (var sceneObject in _objects)
            {
                sceneObject.GetRenderables(_graphics).ForEach(renderable => _frame.Add(renderable));
            }

            _gl.DepthMask(true);
            _gl.Enable(EnableCap.DepthTest);
            _gl.DepthFunc(DepthFunction.Always);
            _gl.DepthRange(0, 1);

            _frame.RenderToView(_graphics, Camera);

            uint snapWidth = 1000;
            uint snapHeight = 1000;
            Span<float> values = new Span<float>(new float[windowWidth * windowHeight]);

            var a = false;
            if (a)
            {
                DumpDepth((int)width, (int)height, @"C:\Users\hugin\Desktop\temp\test.tga");
            }
        }

        public unsafe Vector3 FromScreenSpaceToWorldSpace(uint screenX, uint screenY)
        {
            Span<float> pixels = new float[Camera.Width * Camera.Height];
            _gl.ReadPixels(0, 0, (uint)Camera.Width, (uint)Camera.Height, PixelFormat.DepthComponent, PixelType.Float, pixels);

            var depth = pixels[(int)(Camera.Width * (Camera.Height - 1 - screenY) + screenX)];

            Matrix4x4.Invert(Camera.GetView() * Camera.GetProjection(), out var inv);

            var @in = new Vector4(
                ((float)screenX / (float)Camera.Width * 2f) - 1,
                ((float)(Camera.Height - 1 - screenY) / (float)Camera.Height * 2f) - 1,
                2f * (float)depth - 1.0f,
                1.0f
            );
            var @out = Vector4.Transform(@in, inv); 
            @out.W = 1.0f / @out.W;

            var x = @out.X * @out.W;
            var y = @out.Y * @out.W;
            var z = @out.Z * @out.W;
            return new Vector3(@out.X * @out.W, @out.Y * @out.W, @out.Z * @out.W);
        }

        private unsafe void DumpDepth(int Width, int Height, string filepath)
        {
            Span<float> pixels = new float[Width * Height];
            _gl.ReadPixels(0, 0, (uint)Width, (uint)Height, PixelFormat.DepthComponent, PixelType.Float, pixels);

            var min = pixels.ToArray().Min();
            var max = pixels.ToArray().Max();
            var diff = max - min;

            var imageData = new List<byte>();
            for (int i = 0; i < Width * Height; i++)
            {
                var grey = (pixels[i] - min) / diff;
                imageData.Add((byte)(grey * 255));
                imageData.Add((byte)(grey * 255));
                imageData.Add((byte)(grey * 255));
            }

            TPC tpc = new TPC(Width, Height, TPCTextureFormat.RGB, imageData.ToArray());
            new TGABinaryWriter(filepath).Write(tpc);
        }

        public void AddObject(SceneObject sceneObject)
        {
            _objects.Add(sceneObject);
        }

        private static DebugProc DebugMessageDelegate = OnDebugMessage;
        private static void OnDebugMessage(GLEnum source, GLEnum type, int id, GLEnum severity, int length, nint pMessage, nint pUserParam)
        {
            string message = Marshal.PtrToStringAnsi(pMessage, length);

            if (type == GLEnum.DebugTypeError)
            {
                throw new Exception(message);
            }
        }
    }
}
