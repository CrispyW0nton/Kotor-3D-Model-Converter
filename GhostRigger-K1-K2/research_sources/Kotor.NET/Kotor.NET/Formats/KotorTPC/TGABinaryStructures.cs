using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Extensions;

namespace Kotor.NET.Formats.KotorTPC
{
    public static class TGABinaryStructures
    {
        public class TGA
        {
            public FileHeader FileHeader { get; set; }
            public string ID { get; set; }
            public byte[] ColourMapData { get; set; }
            public byte[] ImageData { get; set; }

            public TGA(BinaryReader reader)
            {
                FileHeader = new(reader);
                ID = reader.ReadString(FileHeader.IDLength);
                ColourMapData = reader.ReadBytes(FileHeader.ColourMapDepth / 8);
                ImageData = reader.ReadBytes(FileHeader.Width * FileHeader.Height * FileHeader.BitsPerPixel / 8);
            }

            public TGA()
            {
                FileHeader = new();
                ID = "";
                ColourMapData = new byte[0];
                ImageData = new byte[0];
            }

            public void SanityCheck()
            {
                Debug.Assert(ColourMapData.Length == FileHeader.ColourMapDepth / 8);
                Debug.Assert(FileHeader.ColourMapType == 0 && FileHeader.ColourMapDepth > 0);
                Debug.Assert(ImageData.Length == FileHeader.BitsPerPixel / 8);
            }

            public void Write(BinaryWriter writer)
            {
                FileHeader.Write(writer);
                writer.Write(ID, 0);
                writer.Write(ColourMapData);
                writer.Write(ImageData);
            }
        }

        public class FileHeader
        {
            public Byte IDLength { get; set; }
            public Byte ColourMapType { get; set; }
            public Byte DataTypeCode { get; set; }
            public UInt16 ColourMapOrigin { get; set; }
            public UInt16 ColourMapLength { get; set; }
            public Byte ColourMapDepth { get; set; }
            public UInt16 XOrigin { get; set; }
            public UInt16 YOrigin { get; set; }
            public UInt16 Width { get; set; }
            public UInt16 Height { get; set; }
            public Byte BitsPerPixel { get; set; }
            public Byte ImageDescriptor { get; set; }

            public FileHeader(BinaryReader reader)
            {
                IDLength = reader.ReadByte();
                ColourMapType = reader.ReadByte();
                DataTypeCode = reader.ReadByte();
                ColourMapOrigin = reader.ReadUInt16();
                ColourMapLength = reader.ReadUInt16();
                ColourMapDepth = reader.ReadByte();
                XOrigin = reader.ReadUInt16();
                YOrigin = reader.ReadUInt16();
                Width = reader.ReadUInt16();
                Height = reader.ReadUInt16();
                BitsPerPixel = reader.ReadByte();
                ImageDescriptor = reader.ReadByte();
            }

            public FileHeader()
            {

            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(IDLength);
                writer.Write(ColourMapType);
                writer.Write(DataTypeCode);
                writer.Write(ColourMapOrigin);
                writer.Write(ColourMapLength);
                writer.Write(ColourMapDepth);
                writer.Write(XOrigin);
                writer.Write(YOrigin);
                writer.Write(Width);
                writer.Write(Height);
                writer.Write(BitsPerPixel);
                writer.Write(ImageDescriptor);
            }
        }

        public enum DataTypeCodes
        {
            NoImageData = 0,
            Uncompressed_ColourMapped = 1,
            Uncompressed_RGB = 2,
            Uncompressed_Greyscale = 3,
            RLE_ColourMapped = 9,
            RLE_RGB = 10,
            Compressed_Greyscale = 11,
            Compressed_ColourMappedA = 32,
            Compressed_ColourMappedB = 33,
        }
    }
}
