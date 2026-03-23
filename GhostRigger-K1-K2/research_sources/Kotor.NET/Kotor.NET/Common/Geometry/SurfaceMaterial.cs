using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Geometry
{
    public enum SurfaceMaterial
    {
        [Walkable(false)]
        Undefined,

        [Walkable(true)]
        Grass,
    }

    public class WalkableAttribute : Attribute
    {
        public bool IsWalkable { get; set; }

        public WalkableAttribute(bool isWalkable)
        {
            IsWalkable = isWalkable;
        }
    }

    public static class SurfaceMaterialExtension
    {
        public static bool IsWalkable(this SurfaceMaterial material)
        {
            var attribute = (WalkableAttribute)typeof(SurfaceMaterial).GetCustomAttributes(typeof(WalkableAttribute), false).Single();
            return attribute.IsWalkable;
        }
    }
}
