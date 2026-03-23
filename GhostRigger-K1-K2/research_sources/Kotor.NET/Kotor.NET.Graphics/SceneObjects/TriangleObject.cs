using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Graphics.Extensions;
using Silk.NET.OpenGLES;

namespace Kotor.NET.Graphics.SceneObjects
{
    public class TriangleObject : SceneObject
    {
        public override List<IRenderable> GetRenderables(Graphics graphics)
        {
            return new() { new Renderable(graphics.GetVAO(":triangle"), graphics.GetShader("kotor"), null, null) };
        }

        public static unsafe void InitializeVertexArray(GL gl, Graphics graphics)
        {
            //float[] vertices =
            //{
            //    -1f, -1f, 0f,
            //     1f, -1f, 0f,
            //     0f,  1f, 0f
            // };
            float[] vertices =
            {
                 0.0f,  0.0f, 0, // Right onw
                 0.5f,  1.0f, 0, // Top one
                 1.0f,  0.0f, 0, // Left one
            };

            ushort[] indices =
            {
                //0, 1, 3,   // first triangle
                //1, 2, 3    // second triangle
                0,1,2
            };

            uint vao = gl.GenVertexArray();
            uint vbo = gl.GenBuffer();
            uint ebo = gl.GenBuffer();

            gl.BindVertexArray(vao);

            gl.BindBuffer(BufferTargetARB.ArrayBuffer, vbo);
            fixed (float* buf = vertices)
                gl.BufferData(BufferTargetARB.ArrayBuffer, (nuint)(vertices.Length * sizeof(float)), buf, BufferUsageARB.StaticDraw);

            gl.VertexAttribPointer(1, 3, VertexAttribPointerType.Float, false, 3 * sizeof(float), (void*)0);
            gl.EnableVertexAttribArray(1);

            gl.BindBuffer(BufferTargetARB.ElementArrayBuffer, ebo);
            fixed (ushort* buf = indices)
                gl.BufferData(BufferTargetARB.ElementArrayBuffer, (nuint)(indices.Length * sizeof(ushort)), buf, BufferUsageARB.StaticDraw);

            graphics.SetVAO(":triangle", new VertexArray(gl, vao, (uint)indices.Length));
        }
    }
}
