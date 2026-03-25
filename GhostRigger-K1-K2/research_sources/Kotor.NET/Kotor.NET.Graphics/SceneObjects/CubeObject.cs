using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using Silk.NET.OpenGLES;

namespace Kotor.NET.Graphics.SceneObjects
{
    public class CubeObject : SceneObject
    {
        public override List<IRenderable> GetRenderables(Graphics graphics)
        {
            return new() { new Renderable(graphics.GetVAO(":cube"), graphics.GetShader("test"), null, null) };
        }

        public static void InitializeVertexArray(GL gl, Graphics graphics)
        {
            float scaleFactor = 1f;

            Vector3[] vertices =
            {
                // front
                new Vector3(-0.5f, -0.5f,  0.5f) * scaleFactor,
                new Vector3( 0.5f, -0.5f,  0.5f) * scaleFactor,
                new Vector3( 0.5f,  0.5f,  0.5f) * scaleFactor,
                new Vector3(-0.5f,  0.5f,  0.5f) * scaleFactor,
                // back
                new Vector3(-0.5f, -0.5f, -0.5f) * scaleFactor,
                new Vector3( 0.5f, -0.5f, -0.5f) * scaleFactor,
                new Vector3( 0.5f,  0.5f, -0.5f) * scaleFactor,
                new Vector3(-0.5f,  0.5f, -0.5f) * scaleFactor,
             };

            short[] elements =
            {
		        // front
		        0, 1, 2,
                2, 3, 0,
		        // right
		        1, 5, 6,
                6, 2, 1,
		        // back
		        7, 6, 5,
                5, 4, 7,
		        // left
		        4, 0, 3,
                3, 7, 4,
		        // bottom
		        4, 5, 1,
                1, 0, 4,
		        // top
		        3, 2, 6,
                6, 7, 3
            };

            graphics.SetVAO(":cube", new VertexArray(gl, vertices, elements));
        }
    }
}
