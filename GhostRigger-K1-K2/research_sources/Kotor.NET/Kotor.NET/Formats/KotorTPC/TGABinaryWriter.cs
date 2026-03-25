
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorSSF;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using static Kotor.NET.Formats.KotorTPC.TGABinaryStructures;

namespace Kotor.NET.Formats.KotorTPC
{
    public class TGABinaryWriter : IWriter<TPC>
    {
        public BinaryWriter? _writer;
        public SSF? _ssf;

        public TGABinaryWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public TGABinaryWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(TPC tpc)
        {
            var bitsPerPixel = (tpc.Format == TPCTextureFormat.DXT5 || tpc.Format == TPCTextureFormat.RGBA)
                ? (byte)32
                : (byte)24;

            byte[] imageData = new byte[0];
            if (tpc.Format == TPCTextureFormat.RGB)
            {
                imageData = tpc.GetMipmap(0).Data;
            }

            var tga = new TGA
            {
                FileHeader = new FileHeader
                {
                    IDLength = 0,
                    ColourMapType = 0,
                    DataTypeCode = 2,
                    ColourMapOrigin = 0,
                    ColourMapLength = 0,
                    XOrigin = 0,
                    YOrigin = 0,
                    Width = (ushort)tpc.Width,
                    Height = (ushort)tpc.Height,
                    BitsPerPixel = bitsPerPixel,
                    ImageDescriptor = 0,
                },
                ImageData = imageData
            };

            tga.Write(_writer);
            _writer.Flush();
            _writer.Close();
        }
    }
}
