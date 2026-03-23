using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Formats.KotorTPC
{
    public class TPC
    {
        public int Width { get; set; }
        public int Height { get; set; }
        public TPCTextureFormat Format {  get; set; }
        public string TXI { get; set; } = "";

        private List<byte[]> _mipmapData = new();

        public TPC(int width, int height, TPCTextureFormat format, byte[] data)
        {
            Width = width;
            Height = height;
            Format = format;
            _mipmapData.Add(data);
        }

        public Mipmap GetMipmap(int index)
        {
            return new Mipmap
            {
                Width = (int)Math.Pow(Width, 1 / (index + 1)),
                Height = (int)Math.Pow(Height, 1 / (index + 1)),
                Data = _mipmapData[index],
            };
        }

        //public Mipmap GetMipmap(int index, TPCTextureFormat format)
        //{
        //    return Convert(GetMipmap(index), Format, format);
        //}

        //private Mipmap Convert(Mipmap mipmap, TPCTextureFormat source, TPCTextureFormat target)
        //{
            
        //}
    }

    public class Mipmap
    {
        public int Width { get; set; }
        public int Height { get; set; }
        public byte[] Data { get; set; }

        public int Size => Data.Length;
    }

    public enum TPCTextureFormat
    {
        Greyscale,
        RGB,
        RGBA,
        DXT1,
        DXT5
    }
}
