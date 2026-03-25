using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Silk.NET.OpenGLES;

namespace Kotor.NET.Graphics
{
    public class Graphics
    {
        public GL GL { get; private set; }

        public Dictionary<string, Shader> Shaders { get; } = new();
        public Dictionary<string, Texture> Textures { get; } = new();
        public Dictionary<string, VertexArray> VAOs { get; } = new();

        public Graphics(GL gl)
        {
            GL = gl;
        }

        public Shader GetShader(string name)
        {
            return Shaders[name];
        }

        public Texture GetTextures(string name)
        {
            return Textures.Single(x => string.Equals(x.Key, name, StringComparison.OrdinalIgnoreCase)).Value;
        }

        public VertexArray GetVAO(string name)
        {
            return VAOs[name];
        }

        public void SetVAO(string name, VertexArray vao)
        {
            VAOs.Add(name, vao);
        }
    }
}
