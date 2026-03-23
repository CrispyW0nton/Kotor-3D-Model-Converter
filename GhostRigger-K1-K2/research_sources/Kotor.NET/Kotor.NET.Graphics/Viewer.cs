using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using OpenTK.Graphics.OpenGL;
using OpenTK.Windowing.Common;
using OpenTK.Windowing.Desktop;

namespace Kotor.NET.Graphics
{
    public class Viewer : IWindow
    {
        public Viewer(int width, int height, string title) : base(GameWindowSettings.Default, new NativeWindowSettings() { Size = (width, height), Title = title }) { }

        public Scene scene;

        protected override void OnUpdateFrame(FrameEventArgs e)
        {
            base.OnUpdateFrame(e);

        }

        protected override void OnLoad()
        {
            base.OnLoad();

            scene = new(new(), null);
            scene.Init();
            //TempOnLoad();
        }

        protected override void OnRenderFrame(FrameEventArgs e)
        {
            base.OnRenderFrame(e);

            //TempRender();
            scene.Render();

            SwapBuffers();
        }

        Shader shader;
        int VertexArrayObject;
        private void TempOnLoad()
        {
            float[] vertices = {
                -0.5f, -0.5f, 0.0f, //Bottom-left vertex
                 0.5f, -0.5f, 0.0f, //Bottom-right vertex
                 0.0f,  0.5f, 0.0f  //Top vertex
            };

            short[] indices =
            {
                0, 1, 2,   // first triangle
            };

            shader = new Shader("kotor");

            GL.Disable(EnableCap.CullFace);


            VertexArrayObject = GL.GenVertexArray();
            GL.BindVertexArray(VertexArrayObject);

            int VertexBufferObject = GL.GenBuffer();
            int ElementBufferObject = GL.GenBuffer();

            GL.BindBuffer(BufferTarget.ArrayBuffer, VertexBufferObject);
            GL.BufferData(BufferTarget.ArrayBuffer, vertices.Length * sizeof(float), vertices, BufferUsageHint.StaticDraw);

            GL.VertexAttribPointer(1, 3, VertexAttribPointerType.Float, false, 3 * sizeof(float), 0);
            GL.EnableVertexAttribArray(1);

            GL.BindBuffer(BufferTarget.ElementArrayBuffer, ElementBufferObject);
            GL.BufferData(BufferTarget.ElementArrayBuffer, indices.Length * sizeof(short), indices, BufferUsageHint.StaticDraw);


            //GL.BindVertexArray(0);
        }
        private void TempRender()
        {
            shader.Use();
            GL.BindVertexArray(VertexArrayObject);
            GL.DrawElements(PrimitiveType.Triangles, 3, DrawElementsType.UnsignedShort, 0);
            //GL.DrawArrays(PrimitiveType.Triangles, 0, 3);

        }
    }

}
