using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorERF;
using Silk.NET.OpenGLES;

namespace Kotor.NET.Graphics
{
    public class Frame
    {
        // list of things to renderss

        private IList<IRenderable> _renderables = new List<IRenderable>();
        private Matrix4x4 _transform = Matrix4x4.Identity;

        public void Add(IRenderable renderable)
        {
            _renderables.Add(renderable);
        }

        public void RenderToView(Graphics graphics, Camera camera)
        {
            graphics.GL.Clear(ClearBufferMask.ColorBufferBit | ClearBufferMask.DepthBufferBit);
            graphics.GL.ClearColor(0, 0, 0.3f, 1);

            foreach (var renderable in _renderables)
            {
                var shader = renderable.Shader;
                shader.Use();

                shader.SetUniformMatrix4x4("view", camera.GetView());
                shader.SetUniformMatrix4x4("projection", camera.GetProjection());
                shader.SetUniformMatrix4x4("model", _transform);

                shader.SetUniformVector3("mousePosition", new(camera.MouseX, camera.MouseY, camera.MouseZ));

                renderable.Render();
            }
            _renderables.Clear();
        }
    }
}
