using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Graphics;
using Kotor.NET.Graphics.SceneObjects;
using MapBuilder.Data;

namespace MapBuilder.Render
{
    public abstract class MapChildObject : SceneObject
    {
        public object Data { get; set; }

        public MapChildObject(object data)
        {
            Data = data;
        }
    }
}
