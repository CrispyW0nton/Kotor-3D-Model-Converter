using Kotor.NET.Common.Conversation;
using Kotor.NET.Common.Data;
using Kotor.NET.Common.Geometry;
using Kotor.NET.Extensions;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Formats.KotorGFF
{
    /// <summary>
    /// Represents the tree data structure of the GFF file format used by
    /// the KotOR game engine.
    /// </summary>
    public class GFF
    {
        public GFFStruct Root { get; set; } = new();

        /// <summary>
        /// Flattens and returns all structs in the GFF tree.
        /// </summary>
        /// <returns>A flat list of all structs.</returns>
        public IEnumerable<GFFStruct> AllStructs()
        {
            var search = new List<GFFStruct> { Root };
            var found = new List<GFFStruct>();

            while (search.Count > 0)
            {
                var take = search.ElementAt(0);
                search.RemoveAt(0);
                found.Add(take);

                var lists = take.Fields.Where(x => x.Type == GFFFieldType.List);
                var structs = take.Fields.Where(x => x.Type == GFFFieldType.Struct);

                foreach (var list in lists)
                {
                    search.AddRange(take.Get<GFFList>(list.Label)!);
                }

                foreach (var @struct in structs)
                {
                    search.Add(take.Get<GFFStruct>(@struct.Label)!);
                }
            }

            return found.ToList();
        }

        /// <summary>
        /// Returns a list of all fields in the GFF tree.
        /// </summary>
        /// <returns>A list of all fields.</returns>
        public List<GFFField> AllFields()
        {
            var found = new List<GFFField>();
            var allStructs = AllStructs();

            foreach (var @struct in allStructs)
            {
                found.AddRange(@struct.Fields);
            }

            return found;
        }
    }

    public class GFFStruct
    {
        public uint ID { get; set; }
        public List<GFFField> Fields { get; private set; }

        public object this[string label]
        {
            get { return Get(label); }
            set { Set(label, value); }
        }

        public GFFStruct()
        {
            ID = 0;
            Fields = new List<GFFField>();
        }

        public GFFStruct(uint id)
        {
            ID = id;
            Fields = new List<GFFField>();
        }

        public GFFField Get(string label)
        {
            return Fields.Single(x => x.Label == label);
        }

        public T Get<T>(string label, T fallback)
        {
            var field = Fields.SingleOrDefault(x => x.Label == label);

            return (T)field!.Value ?? fallback;
        }

        public T? Get<T>(string label)
        {
            var field = Fields.SingleOrDefault(x => x.Label == label);

            return (T)field!.Value;
        }

        public void Set<T>(string label, T value)
        {
            Fields.RemoveAll(x => x.Label == label);
            Fields.Add(new GFFField(label, value));
        }

        public bool Has(string label)
        {
            return (Fields.FirstOrDefault(x => x.Label == label) != null) ? true : false;
        }

        public Byte GetUInt8(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.UInt8)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (Byte)field.Value;
        }
        public Byte GetUInt8(string label, Byte fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.UInt8)
                return fallback;

            return (Byte)field.Value;
        }
        public SByte GetInt8(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Int8)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (SByte)field.Value;
        }
        public SByte GetInt8(string label, SByte fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Int8)
                return fallback;

            return (SByte)field.Value;
        }
        public UInt16 GetUInt16(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.UInt16)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (UInt16)field.Value;
        }
        public UInt16 GetUInt16(string label, UInt16 fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.UInt16)
                return fallback;

            return (UInt16)field.Value;
        }
        public Int16 GetInt16(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Int16)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (Int16)field.Value;
        }
        public Int16 GetInt16(string label, Int16 fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Int16)
                return fallback;

            return (Int16)field.Value;
        }
        public UInt32 GetUInt32(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.UInt32)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (UInt32)field.Value;
        }
        public UInt32 GetUInt32(string label, UInt32 fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.UInt32)
                return fallback;

            return (UInt32)field.Value;
        }
        public Int32 GetInt32(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Int32)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (Int32)field.Value;
        }
        public Int32 GetInt32(string label, Int32 fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Int32)
                return fallback;

            return (Int32)field.Value;
        }
        public UInt64 GetUInt64(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.UInt64)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (UInt64)field.Value;
        }
        public UInt64 GetUInt64(string label, UInt64 fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.UInt64)
                return fallback;

            return (UInt64)field.Value;
        }
        public Int64 GetInt64(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Int64)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (Int64)field.Value;
        }
        public Int64 GetInt64(string label, Int64 fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Int64)
                return fallback;

            return (Int64)field.Value;
        }
        public Single GetSingle(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Single)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (Single)field.Value;
        }
        public Single GetSingle(string label, Single fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Single)
                return fallback;

            return (Single)field.Value;
        }
        public Double GetDouble(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Double)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (Double)field.Value;
        }
        public Double GetDouble(string label, Double fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Double)
                return fallback;

            return (Double)field.Value;
        }
        public String GetString(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.String)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (String)field.Value;
        }
        public String GetString(string label, String fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.String)
                return fallback;

            return (String)field.Value;
        }
        public LocalizedString GetLocalizedString(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.LocalizedString)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (LocalizedString)field.Value;
        }
        public LocalizedString GetLocalizedString(string label, LocalizedString fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.LocalizedString)
                return fallback;

            return (LocalizedString)field.Value;
        }
        public ResRef GetResRef(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.ResRef)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (ResRef)field.Value;
        }
        public ResRef GetResRef(string label, ResRef fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.ResRef)
                return fallback;

            return (ResRef)field.Value;
        }
        public byte[] GetBinary(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Binary)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (byte[])field.Value;
        }
        public byte[] GetBinary(string label, byte[] fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Binary)
                return fallback;

            return (byte[])field.Value;
        }
        public GFFList GetList(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.List)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (GFFList)field.Value;
        }
        public GFFList GetList(string label, GFFList fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.List)
                return fallback;

            return (GFFList)field.Value;
        }
        public GFFStruct GetStruct(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Struct)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (GFFStruct)field.Value;
        }
        public GFFStruct GetStruct(string label, GFFStruct fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Struct)
                return fallback;

            return (GFFStruct)field.Value;
        }
        public Vector3 GetVector3(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Vector3)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (Vector3)field.Value;
        }
        public Vector3 GetVector3(string label, Vector3 fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Vector3)
                return fallback;

            return (Vector3)field.Value;
        }
        public Vector4 GetVector4(string label)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                throw new ArgumentException("Field with that label does not exist");
            if (field.Type != GFFFieldType.Vector3)
                throw new ArgumentException("Field with that label was not of the correct type.");

            return (Vector4)field.Value;
        }
        public Vector4 GetVector4(string label, Vector4 fallback)
        {
            var field = Fields.SingleOrDefault(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));

            if (field == null)
                return fallback;
            if (field.Type != GFFFieldType.Vector3)
                return fallback;

            return (Vector4)field.Value;
        }

        public void SetUInt8(string label, Byte value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetInt8(string label, SByte value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetUInt16(string label, UInt16 value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetInt16(string label, Int16 value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetUInt32(string label, UInt32 value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetInt32(string label, Int32 value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetUInt64(string label, UInt64 value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetInt64(string label, Int64 value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetSingle(string label, Single value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetDouble(string label, Double value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetString(string label, String value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");
            if (value is null)
                throw new ArgumentException("GFF fields cannot have a null value.");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetResRef(string label, ResRef value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");
            if (value is null)
                throw new ArgumentException("GFF fields cannot have a null value.");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetBinary(string label, byte[] value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");
            if (value is null)
                throw new ArgumentException("GFF fields cannot have a null value.");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetLocalizedString(string label, LocalizedString value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");
            if (value is null)
                throw new ArgumentException("GFF fields cannot have a null value.");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public GFFStruct SetStruct(string label, GFFStruct value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");
            if (value is null)
                throw new ArgumentException("GFF fields cannot have a null value.");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));

            return value;
        }
        public GFFList SetList(string label, GFFList value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");
            if (value is null)
                throw new ArgumentException("GFF fields cannot have a null value.");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));

            return value;
        }
        public void SetVector3(string label, Vector3 value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");
            if (value is null)
                throw new ArgumentException("GFF fields cannot have a null value.");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
        public void SetVector4(string label, Vector4 value)
        {
            if (label.Length > 16)
                throw new ArgumentException("Labels cannot exceed 16 characters");
            if (value is null)
                throw new ArgumentException("GFF fields cannot have a null value.");

            Fields.RemoveAll(x => string.Equals(x.Label, label, StringComparison.OrdinalIgnoreCase));
            Fields.Add(new GFFField(label, value));
        }
    }

    public class GFFField
    {
        public static readonly IReadOnlyDictionary<GFFFieldType, Type> TYPE_MAPPING = new Dictionary<GFFFieldType, Type>()
        {
            [GFFFieldType.UInt8] = typeof(Byte),
            [GFFFieldType.Int8] = typeof(SByte),
            [GFFFieldType.UInt16] = typeof(UInt16),
            [GFFFieldType.Int16] = typeof(Int16),
            [GFFFieldType.UInt32] = typeof(UInt32),
            [GFFFieldType.Int32] = typeof(Int32),
            [GFFFieldType.UInt64] = typeof(UInt64),
            [GFFFieldType.Int64] = typeof(Int64),
            [GFFFieldType.Single] = typeof(Single),
            [GFFFieldType.Double] = typeof(Double),
            [GFFFieldType.String] = typeof(String),
            [GFFFieldType.ResRef] = typeof(ResRef),
            [GFFFieldType.LocalizedString] = typeof(LocalizedString),
            [GFFFieldType.Binary] = typeof(Byte[]),
            [GFFFieldType.Struct] = typeof(GFFStruct),
            [GFFFieldType.List] = typeof(GFFList),
            [GFFFieldType.Vector3] = typeof(Vector3),
            [GFFFieldType.Vector4] = typeof(Vector4),
        };

        private object _value;

        public string Label { get; set; }
        public object Value
        {
            get => _value;
            set
            {
                _value = value;
            }
        }
        public GFFFieldType Type { get => TYPE_MAPPING.FirstOrDefault(x => x.Value == Value.GetType()).Key; }

        public GFFField(string label, object value)
        {
            Label = label;
            Value = _value = value;
        }
    }

    public class GFFList : ICollection<GFFStruct>
    {
        private List<GFFStruct> _list = new();

        public int Count => _list.Count;

        public bool IsReadOnly => false;

        public void Add(GFFStruct item)
        {
            _list.Add(item);
        }
        public GFFStruct Add()
        {
            var item = new GFFStruct();
            _list.Add(item);
            return item;
        }

        public void Clear()
        {
            _list.Clear();
        }

        public bool Contains(GFFStruct item)
        {
            return _list.Contains(item);
        }

        public void CopyTo(GFFStruct[] array, int arrayIndex)
        {
            _list.CopyTo(array, arrayIndex);
        }

        public IEnumerator<GFFStruct> GetEnumerator()
        {
            return _list.GetEnumerator();
        }

        public bool Remove(GFFStruct item)
        {
            return _list.Remove(item);
        }

        IEnumerator IEnumerable.GetEnumerator()
        {
            return _list.GetEnumerator();
        }

        public GFFStruct Get(int index)
        {
            var element = _list.ElementAtOrDefault(index);

            if (element == null)
            {
                return new();
            }
            else
            {
                return element;
            }
        }
    }

    public enum GFFFieldType
    {
        UInt8,
        Int8,
        UInt16,
        Int16,
        UInt32,
        Int32,
        UInt64,
        Int64,
        Single,
        Double,
        String,
        ResRef,
        LocalizedString,
        Binary,
        Struct,
        List,
        Vector4,
        Vector3,
    }

    public class GFFNavigator
    {
        private object _position;

        public GFFNavigator(GFF gff)
        {
            _position = gff.Root;
        }

        public GFFNavigator(GFFStruct gffStruct)
        {
            _position = gffStruct;
        }

        public GFFNavigator(GFFList gffList)
        {
            _position = gffList;
        }

        public object Resolve()
        {
            return _position;
        }

        public void NavigateTo(string fieldNameOrListIndex)
        {
            if (_position is GFFStruct gffStruct)
            {
                if (gffStruct.Has(fieldNameOrListIndex))
                {
                    _position = gffStruct.Get<object>(fieldNameOrListIndex)!;
                }
                else
                {
                    throw new ArgumentException("Trying to navigate to a field that does not exist.");
                }
            }
            else if (_position is GFFList gffList)
            {
                if (fieldNameOrListIndex.IsInt32())
                {
                    var index = Convert.ToInt32(fieldNameOrListIndex);

                    if (gffList.Count <= index)
                    {
                        throw new ArgumentException("The index specified was greater than the number of structs in the list.");
                    }
                    else
                    {
                        _position = gffList.Get(index);
                    }
                }
                else
                {
                    throw new ArgumentException("Trying to navigate through a list, but a non-integer value was given as an index.");
                }
            }
            else
            {
                throw new ArgumentException("Cannot navigate any further.");
            }
        }
    }
}
