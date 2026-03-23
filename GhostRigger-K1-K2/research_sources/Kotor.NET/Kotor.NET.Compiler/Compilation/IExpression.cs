using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Scripting.Calculator;

namespace Kotor.NET.Scripting.Compilation
{
    public interface IExpression : ASTNode
    {
        public DataType GetDataType();
    }
}
