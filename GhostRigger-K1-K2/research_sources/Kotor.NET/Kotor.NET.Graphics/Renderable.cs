using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Graphics
{
    public class Renderable : IRenderable
    {
        public Shader Shader { get; }

        public Texture Texture1 { get; }

        public Texture Texture2 { get; }

        public VertexArray VAO { get; }

        public Renderable(VertexArray vao, Shader shader, Texture? texture1, Texture? texture2)
        {
            VAO = vao;
            Shader = shader;
            Texture1 = texture1;
            Texture2 = texture2;
        }

        public void Render()
        {
            if (Texture1 is not null)
                Texture1.Use();

            Shader.Use();
            VAO.Draw();
        }
    }
}
