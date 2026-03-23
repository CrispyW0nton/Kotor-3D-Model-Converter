using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Graphics.SceneObjects
{
    public class KotorObject : SceneObject
    {
        public List<KotorObject> Children { get; set; }
        public string VAOKey { get; set; }
        public string Texture { get; set; }
        public string Name { get; set; }
        public bool Render { get; set; }

        public KotorObject(string vaoKey, string texture1)
        {
            Children = new();
            VAOKey = vaoKey;
            Texture = texture1;
        }

        public override List<IRenderable> GetRenderables(Graphics graphics)
        {
            var renderables = new List<IRenderable>();

            if (VAOKey is not null)
            {
                var vao = graphics.GetVAO(VAOKey);
                var shader = graphics.GetShader("kotor");
                Texture texture1 = graphics.GetTextures(Texture);
                Texture texture2 = null;
                renderables.Add(new Renderable(vao, shader, texture1, texture2));
            }

            renderables.AddRange(Children.SelectMany(x => x.GetRenderables(graphics)));

            return renderables;
        }
    }
}
