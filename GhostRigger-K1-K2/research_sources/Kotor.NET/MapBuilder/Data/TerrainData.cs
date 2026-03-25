using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Graphics.SceneObjects;
using MapBuilder.Render;

namespace MapBuilder.Data
{
    public class TerrainData : Placement
    {
        public uint Width => _width;
        public uint Length => _length;
        public float[,] Height => _height;

        private uint _width;
        private uint _length;
        private float[,] _height;

        public TerrainData(uint width, uint length)
        {
            _width = width;
            _length = length;
            _height = new float[width, length];

            AssignRandomElevation();
        }

        public void AssignRandomElevation()
            {
                var height = new float[Width, Length];
                for (var x = 0; x < Width; x++)
                for (var y = 0; y < Length; y++)
                {
                _height[x, y] = (float)new Random().NextDouble() / 2;
            }
        }

        public override int GetHashCode()
        {
            int hash = 0;
        
            hash ^= _width.GetHashCode();
            hash ^= _height.GetHashCode();

            foreach (var item in _height)
        {
                hash ^= item.GetHashCode();
            }

            return hash;
        }
    }
}
