using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Graphics;
using Kotor.NET.Graphics.SceneObjects;
using MapBuilder.Data;
using static System.Runtime.InteropServices.JavaScript.JSType;

namespace MapBuilder.Render
{
    public class MapObject : SceneObject
    {
        public MapData MapData { get; set; } = new();
        public List<MapChildObject> Children { get; set; } = new();

        private Graphics _graphics;

        public MapObject(Graphics graphics)
        {
            _graphics = graphics;
        }

        public void RefreshChildren()
        {
            // What has been added?
            foreach (var placement in MapData.Placements)
            {
                if (!Children.Select(x => x.Data).Contains(placement))
                {
                    Children.Add(Generate(placement as dynamic));
                }
            }

            // What has been removed?
            Children.ForEach(child =>
            {
                if (!MapData.Placements.Contains(child.Data))
                {
                    Children.Remove(child);
                }
            });
        }

        public override List<IRenderable> GetRenderables(Graphics graphics)
        {
            RefreshChildren();
            return Children.SelectMany(x => x.GetRenderables(graphics)).ToList();
        }

        public MapChildObject Generate(TerrainData data)
        {
            return new TerrainObject(_graphics, data);
        }
    }
}
