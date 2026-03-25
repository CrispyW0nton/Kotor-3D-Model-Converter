// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Extensions;
using Kotor.NET.Formats.KotorTLK;

namespace Kotor.NET.Common
{
    /// <summary>
    /// Efficiently load up to date talk table entries from a TLK file. Every
    /// time an entry is loaded, the file is reopened and only the necessary
    /// data is pulled into memory.
    /// </summary>
    public class TalkTable
    {
        /// <summary>
        /// The filepath of the TLK file.
        /// </summary>
        public string FilePath { get; private set; }

        public TalkTable(string filepath)
        {
            FilePath = filepath;
        }

        /// <summary>
        /// Return a single entry matching the specified stringref.
        /// </summary>
        /// <param name="stringref">The stringref of the entry to find.</param>
        /// <returns>A talk table entry.</returns>
        public TalkTableEntry Get(int stringref)
        {
            using (var stream = File.OpenRead(FilePath))
            using (var reader = new BinaryReader(stream))
            {
                reader.BaseStream.Position = 12;
                var stringCount = reader.ReadInt32();
                var stringEntriesOffset = reader.ReadInt32();

                reader.BaseStream.Position = 20 + (40 * stringref);
                var flags = reader.ReadInt32();
                var sound = reader.ReadResRef();
                var volumeVariance = reader.ReadInt32();
                var pitchVariance = reader.ReadInt32();
                var textOffset = reader.ReadInt32();
                var textLength = reader.ReadInt32();
                var soundLength = reader.ReadInt32();

                reader.BaseStream.Position = stringEntriesOffset + textOffset;
                var text = reader.ReadString(textLength);

                return new TalkTableEntry(text, sound);
            }
        }

        /// <summary>
        /// Return a multiple entries matching matching the given stringrefs.
        /// </summary>
        /// <param name="stringrefs">A list of stringrefs to find.</param>
        /// <returns>A dictionary mapping stringrefs to the found entries.</returns>
        public IDictionary<int, TalkTableEntry> Get(IEnumerable<int> stringrefs)
        {
            var entries = new Dictionary<int, TalkTableEntry>();

            using (var stream = File.OpenRead(FilePath))
            using (var reader = new BinaryReader(stream))
            {
                reader.BaseStream.Position = 12;
                var stringCount = reader.ReadInt32();
                var stringEntriesOffset = reader.ReadInt32();

                foreach (var stringref in stringrefs)
                {
                    reader.BaseStream.Position = 20 * (40 * stringref);
                    var flags = reader.ReadInt32();
                    var sound = reader.ReadResRef();
                    var volumeVariance = reader.ReadInt32();
                    var pitchVariance = reader.ReadInt32();
                    var textOffset = reader.ReadInt32();
                    var textLength = reader.ReadInt32();
                    var soundLength = reader.ReadInt32();

                    reader.BaseStream.Position = stringEntriesOffset + textOffset;
                    var text = reader.ReadString(textLength);

                    var entry = new TalkTableEntry(text, sound);
                    entries.Add(stringref, entry);
                }
            }

            return entries;
        }

        /// <summary>
        /// Returns how many entries are in the talk table.
        /// </summary>
        /// <returns></returns>
        public int Size()
        {
            using (var stream = File.OpenRead(FilePath))
            using (var reader = new BinaryReader(stream))
            {
                reader.BaseStream.Position = 12;
                var stringCount = reader.ReadInt32();

                return stringCount;
            }
        }

        /// <summary>
        /// Returns the language of the talk table.
        /// </summary>
        /// <returns></returns>
        public Language Language()
        {
            using (var stream = File.OpenRead(FilePath))
            using (var reader = new BinaryReader(stream))
            {
                reader.BaseStream.Position = 8;
                var languageID = reader.ReadInt32();

                return (Language)languageID;
            }
        }

        /// <summary>
        /// Sets the text of the entry matching the stringref.
        /// </summary>
        /// <param name="stringref">The stringref of the target entry.</param>
        /// <param name="text">The new text for the entry.</param>
        public void Set(int stringref, string text)
        {
            var tlk = new TLKBinaryReader(FilePath).Read();
            tlk.Get(stringref).Text = text;

            new TLKBinaryWriter(FilePath).Write(tlk);
        }

        /// <summary>
        /// Sets the text and resref of the entry matching the stringref.
        /// </summary>
        /// <param name="stringref">The stringref of the target entry.</param>
        /// <param name="text">The new text for the entry.</param>
        /// <param name="resref">The new resref for the entry.</param>
        public void Set(int stringref, string text, ResRef resref)
        {
            var tlk = new TLKBinaryReader(FilePath).Read();
            tlk.Get(stringref).Text = text;
            tlk.Get(stringref).ResRef = resref;

            new TLKBinaryWriter(FilePath).Write(tlk);
        }
    }
}
